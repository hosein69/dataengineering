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

rem Fonts: Ravi first, then IRANSans. Licensed files are in assets\fonts in the package root
rem (see assets\fonts\README_FA.md). Installed system fonts are never embedded in sent HTML.
rem set "GSI_FONT_DIR=D:\GSI_APP\assets\fonts"
rem Persian digits in regular-weight text too (default: Latin digits for codes and amounts):
rem set "GSI_FONT_FANUM=1"
rem Do not embed the font in HTML sent to others:
rem set "GSI_EMBED_FONTS=0"
rem No FX lifecycle summary/attachment in e-mails:
rem set "GSI_EMAIL_FX=0"
