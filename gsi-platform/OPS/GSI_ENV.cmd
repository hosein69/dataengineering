@echo off
rem ================================================================
rem GSI operational DWH environment - safe overlay, no core changes
rem This file is intended to be CALLED by scripts in this OPS folder.
rem ================================================================
set "GSI_DATA_ROOT=D:\GSI_DATA"
set "GSI_DWH_PATH=%GSI_DATA_ROOT%\warehouse.sqlite"

rem Optional: keep historical/legacy warehouse physically separate.
rem set "GSI_HISTORICAL_WAREHOUSE_PATH=%GSI_DATA_ROOT%\history\historical_warehouse.sqlite3"

rem Optional: override source roots only when the built-in IKCO paths do not resolve.
rem set "GSI_FOREIGN=\\ikco.com\data-share\Global Sourcing\03-Data\01-Foreign"
rem set "GSI_BLS=\\ikco.com\data-share\Global Sourcing\03-Data\01-Foreign\BLs TOTAL"
rem set "GSI_CLEARANCE=\\ikco.com\data-share\Global Sourcing\03-Data\01-Foreign\BLs TOTAL\Clearance"
rem set "GSI_HR=\\ikco.com\data-share\Global Sourcing\11-Governance & Integration\03-Reports\01-HR"
rem set "GSI_GS_FULL_CHAIN=\\ikco.com\data-share\Global Sourcing\11-Governance & Integration\DataTeam\Data_Ware_House\GS_Full Chain"
rem set "GSI_GS_COMBINE=\\ikco.com\data-share\Global Sourcing\11-Governance & Integration\DataTeam\Data_Ware_House\GS_Combine\OUTPUT"
rem set "GSI_ESMAEILI=\\ikco.com\data-share\Global Sourcing\11-Governance & Integration\25-H.Esmaeili"
rem set "GSI_MOHAMADI=\\ikco.com\data-share\Global Sourcing\11-Governance & Integration\26-M.Mohamadi"
