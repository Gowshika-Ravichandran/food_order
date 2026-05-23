@echo off
setlocal

if not exist sdk mkdir sdk

echo Exporting FastAPI OpenAPI schema...
call venv\Scripts\activate.bat
python -c "import json; from backend.main import app; open('openapi.json', 'w', encoding='utf-8').write(json.dumps(app.openapi(), indent=2))"
if errorlevel 1 (
  echo Failed to export OpenAPI schema.
  exit /b 1
)

where java >nul 2>nul
if errorlevel 1 (
  echo Java is required by OpenAPI Generator CLI but was not found on PATH.
  echo Install Java 17 or later, then run generate_sdk.bat again.
  exit /b 1
)

echo Generating Python SDK with OpenAPI Generator CLI...
npx --yes @openapitools/openapi-generator-cli generate -i openapi.json -g python -o sdk\python --additional-properties=packageName=food_order_sdk

if errorlevel 1 (
  echo SDK generation failed.
  exit /b 1
)

echo Python SDK generated in sdk\python.
endlocal
