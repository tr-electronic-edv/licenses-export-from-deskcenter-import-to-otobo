-- get contracts and its licenses
SELECT
	C.SlmContract_GeneratedDisplayValue,
	L.SlmLicense_GeneratedDisplayValue,
	K.SlmProductKey_Key,
	L.SlmLicense_Quantity,
	L.SlmLicense_EndDate,
	U.User_LoginName
FROM dt_SlmContract C
FULL JOIN dt_SlmLicense L
	ON C.SlmContract_Id = L.SlmLicense_SlmContract_Id
LEFT JOIN dt_SlmProductKey K
	ON	K.SlmProductKey_SlmLicense_Id = L.SlmLicense_Id
LEFT JOIN dt_SlmUserAssignment UA
	ON UA.SlmUserAssignment_SlmLicense_Id = L.SlmLicense_Id
LEFT JOIN dt_User U
	ON UA.SlmUserAssignment_User_Id = U.User_Id
;
-- save the output into CSV file with ; delimiter ;
