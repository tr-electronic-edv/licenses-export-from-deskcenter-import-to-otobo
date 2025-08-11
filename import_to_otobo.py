from peewee import *
import datetime
import csv
from dataclasses import dataclass

print("""
This program imports Contracts, Licenses, Keys and License Users data 
from Deskcenter DB backup (in a CSV file)
and uploads them into the Otobo database.
""")


# Configitem class_id (from 'general_catalog' table)
CONTRACT = 48
LICENSE  = 55
CONTRACT_DEFINITION = 36
LICENSE_DEFINITION = 52
DESCRIPTION_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
    <style></style>
</head>
<body class="ck-content">{description}</body>
</html>
"""

db = MySQLDatabase('otobo_db', host='otobo_server', port=3306, user='otobo_user', password='otobo_password')


class Item(Model):
    configitem_number = CharField()  # e.g. 0048000001 - 48 is class id, 000001 - item_id
    class_id = IntegerField()  # CONTRACT | LICENSE
    last_version_id = IntegerField(default=None)
    cur_depl_state_id = IntegerField(default=27)
    cur_inci_state_id = IntegerField(default=1)
    create_time = DateTimeField(default=datetime.datetime.now)
    create_by = SmallIntegerField(default=2)
    change_time = DateTimeField(default=datetime.datetime.now)
    change_by = SmallIntegerField(default=2)

    def __str__(self):
        if self.class_id == CONTRACT:
            t = "Contract"
        elif self.class_id == LICENSE:
            t = "License"
        else:
            t = "ConfigItem"
        return f"{t} {self.configitem_number}"

    class Meta:
        database = db
        table_name = "configitem"
        

class Version(Model):
    def __init__(self, *args, **kwargs):
        assert kwargs["definition_id"] in [CONTRACT_DEFINITION,LICENSE_DEFINITION], "invalid definition_id"
        super().__init__(*args, **kwargs)

    configitem_id = IntegerField()
    name = CharField()
    version_string = CharField(default="1")
    definition_id = SmallIntegerField()  # 52 for License, 36 for Contract
    depl_state_id = SmallIntegerField(default=27)
    inci_state_id = SmallIntegerField(default=1)
    description = TextField(default="")
    create_time = DateTimeField(default=datetime.datetime.now)
    create_by = SmallIntegerField(default=2)
    change_time = DateTimeField(default=datetime.datetime.now)
    change_by = SmallIntegerField(default=2)

    def __str__(self):
        return f"Version: {self.name}"

    class Meta:
        database = db
        table_name = "configitem_version"


class Counter(Model):
    class_id = SmallIntegerField(primary_key=True)
    counter_type = CharField()
    counter = CharField()

    def __str__(self):
        return str(self.counter)
    
    # counter increment (override += method)
    def increment(self):
        self.counter = str(int(self.counter) + 1)
        self.save()

    class Meta:
        database = db
        table_name = "configitem_counter"


class Link(Model):
    link_type_id = SmallIntegerField(default=6)
    source_configitem_id = ForeignKeyField(Item, backref='link source')
    # source_configitem_version_id = IntegerField(default=None)
    target_configitem_id = ForeignKeyField(Item, backref='link target')
    # target_configitem_version_id = IntegerField(default=None)
    dynamic_field_id = SmallIntegerField(default=None)
    create_time = DateTimeField(default=datetime.datetime.now)
    create_by = CharField(default='1')

    class Meta:
        database = db
        table_name = "configitem_link"


class LinkRelation(Model):
    source_object_id = CharField(default='3')  # link_object class = 3 (ITSMConfigItem)
    source_key = CharField()
    target_object_id = CharField(default='3')  # link_object class = 3 (ITSMConfigItem)
    target_key = CharField()
    type_id = CharField(default='6')  # 6 - "connected to"
    state_id = CharField(default='1')
    create_time = DateTimeField(default=datetime.datetime.now)
    create_by = CharField(default='2')

    class Meta:
        database = db
        table_name = "link_relation"

class ItemHistory(Model):
    configitem_id = CharField()
    content = CharField()
    create_by = CharField(default='2')
    create_time = DateTimeField(default=datetime.datetime.now)
    type_id = CharField(default='3')

    class Meta:
        database = db
        table_name = "configitem_history"


def link_items(source, target):
    """ Create a link between Items """
    # create link_relation
    LinkRelation.create(source_key=str(source.id), target_key=str(target.id))
    # create configitem_link
    Link.create(source_configitem_id=str(source.id), target_configitem_id=str(target.id))
    # show link in source object view
    ItemHistory.create(configitem_id=str(source.id), content=f"{target.id}%%ITSMConfigItem")
    # show link in target object view
    ItemHistory.create(configitem_id=str(target.id), content=f"{source.id}%%ITSMConfigItem")


class DynamicFieldValue(Model):
    """ represents Otobo dynamic fields, License use DynFields to save data like
        Key, Number of Keys, enddate, etc"""
    field_id = IntegerField()
    object_id = ForeignKeyField(Item, backref='dynamic_field')
    value_text = TextField()
    value_date = DateTimeField()

    class Meta:
        database = db
        table_name = "dynamic_field_value"

@dataclass
class FieldId:
    ''' collection of IDs for differend dynamic fields, taken from Otobo DB'''
    LICENSE_KEY = 89
    LICENSE_QUANTITY = 143
    LICENSE_TYPE = 106
    LICENSE_END = 58
    CONTRACT_TYPE = 117


print("Connect to Otobo DB.")
db.connect()

## get current counter and configitem_number values
# for contracts
try:
    last_contract = Item.select().where(Item.class_id == CONTRACT).order_by(Item.configitem_number.desc()).get()
    current_contract_number = int(last_contract.configitem_number)
except DoesNotExist:
    # Otobo CMDB uses "004800000x" numeration for Contracts, where 48 is the ConfigItem code for Contracts
    # as no Contracts has been found, the current contract number is 0
    current_contract_number = 48000000

contracts_counter = Counter.select().where(Counter.class_id == CONTRACT).get()

# for licenses
try:
    last_license = Item.select().where(Item.class_id == LICENSE).order_by(Item.configitem_number.desc()).get()
    current_license_number = int(last_license.configitem_number)
except DoesNotExist:
    # Otobo CMDB uses "005500000x" numeration for Licenses, where 55 is the ConfigItem code for License
    current_license_number = 55000000

licenses_counter = Counter.select().where(Counter.class_id == LICENSE).get()

print(f"Contracts {contracts_counter}, Licenses {licenses_counter}")


def new_contract(name):
    """ This Factory creates a Contract with a proper
        Configitem_number and definition_id.
        Also creates Contract desctiption in a linked Configitem_version object
    """
    print(f"Contract:, {name}")

    global contracts_counter
    contracts_counter.increment()
    
    global current_contract_number
    current_contract_number += 1

    contract = Item.create(configitem_number = f"00{current_contract_number}", class_id = CONTRACT)
    contract_version = Version.create(configitem_id = contract.id, name=name, definition_id=CONTRACT_DEFINITION)
    contract.last_version_id = contract_version.id
    contract.save()
    return contract, contract_version


# def new_license(name, description, license_type, key=None, quantity=None, expiry_date=None):
def new_license(name, description, expiry_date=None, key=None, quantity=None):
    """ This Factory creates a License with a proper
        Configitem_number and definition_id.
        Also creates License desctiption in a linked Configitem_version object.
        Creates a link to a Contract, if one is given
    """
    date = f', Date {expiry_date}' if expiry_date else ''
    print(f"    License: {name};\t{description}{date}")

    global current_license_number
    global licenses_counter

    licenses_counter.increment()
    current_license_number += 1

    license = Item.create(configitem_number = f"00{current_license_number}", class_id = LICENSE)
    license_version = Version.create(configitem_id = license.id, name=name, definition_id=LICENSE_DEFINITION,
        description=DESCRIPTION_TEMPLATE.format(description = description))
    license.last_version_id = license_version.id
    license.save()


    # fill dynamic fields
    if expiry_date:
        DynamicFieldValue.create(field_id=FieldId.LICENSE_END, object_id=license, value_date=expiry_date)
    # if license_type:
    #     DynamicFieldValue.create(field_id=FieldId.LICENSE_TYPE, object_id=license, value_text = license_type)
    if key:
        DynamicFieldValue.create(field_id=FieldId.LICENSE_KEY, object_id=license, value_text = key)
    if quantity:
        DynamicFieldValue.create(field_id=FieldId.LICENSE_QUANTITY, object_id=license, value_text = quantity)

    return license, license_version


def append_to_license_description(license_version, update):
    """ add new data to description """
    print(f"\t{update}")

    # get current data
    data = license_version.description

    # # license description is a html document. We only need the inhalt from the <body> tag.
    data = data.split('<body class="ck-content">')[1]  # remove all before body
    data = data.split('</body>')[0]  # remove all after body

    # append new info
    new_data = f"{data}\n{update}"

    # save united data
    license_version.description = DESCRIPTION_TEMPLATE.format(description=new_data)
    license_version.change_time = datetime.datetime.now()
    license.change_time = datetime.datetime.now()
    license_version.save()
    license.save()


# loading backup CSV file with Contracts and Licenses
with open("contracts_licenses_backup.csv", newline='') as f:
    data = csv.reader(f, delimiter=";")

    contract = None
    contract_version = None
    license = None
    license_version = None
    key = None
    User = None
    
    for row in data:
        # convert 'NULL' csv values to python's None license_type
        cleaned_row = [None if cell.strip().lower() == 'null' else cell for cell in row]
        # Unpack CSV row:
        # Contract, License, Key, Quantity, ExpiryDate, User
        C, L, K, Q, ED, U = cleaned_row
        
        # Import contracts
        if C:
            # is it same contract?
            if contract and contract_version.name == C:
                pass
            else:
                contract, contract_version = new_contract(C)

        # Import licenses
        if L:
            # format license info
            license_description = "<p>"
            # is there a new key?
            if K and K != key:
                key = f"{K}"  # remember key for the next row
                license_description += f"{key}<br>"
            if Q: license_description += f" Quantity {Q}"
            if U: license_description += f" User: {U}"
            license_description += "</p>"
            # convert string 2020-03-11 00:00:00.0000000 into datetime
            expiry_date = datetime.datetime.strptime(ED.split('.')[0], '%Y-%m-%d %H:%M:%S') if ED else None
 
            # is it same license?
            if license and license_version.name == L:
                # append new data
                append_to_license_description(license_version, license_description)
            else:
                # create new License
                license, license_version = new_license(L, description=license_description, expiry_date=expiry_date,
                                                        key=K, quantity=Q)
                
                license_first_word = L.split(" ")[0].lower()
                contract_name = contract_version.name.lower()
                # Two ways to define if license belongs to contract:
                # 1. if contract and license are in the same ROW
                if C and L:
                    print(f"\tLink: {contract} to {license} - both in same row")
                    link_items(contract, license)
                # 2. if the first word in license name is in the contract name
                elif contract and license_first_word in contract_name:
                    print(f"\tLink: {contract} to {license} - name '{license_first_word}' is in Contract name '{contract_name}'")
                    link_items(contract, license)
    
    print(f"Imported {contracts_counter} contracts and {licenses_counter} licenses")

db.close()

print('Reset Otobo Cache!!!:\n\t su -c "/opt/otobo/bin/otobo.Console.pl Maint::Cache::Delete" otobo')
