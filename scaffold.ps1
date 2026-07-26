Set-Location 'c:\Users\user5\OneDrive\Desktop\Trading Bot\nexus-ai'

# Create all module directories with __init__.py stubs
$moduleNames = @(
    "microstructure",
    "chain_intelligence",
    "technical_analysis",
    "price_action",
    "volume_analysis",
    "volatility_engine",
    "macro_engine",
    "global_markets",
    "news_intelligence",
    "social_intelligence",
    "corporate_events",
    "calendar_intelligence",
    "ml_engine",
    "feature_engineering",
    "regime_detection",
    "risk_management",
    "backtesting",
    "explainable_ai",
    "decision_engine",
    "alert_engine"
)

foreach ($mod in $moduleNames) {
    $path = "modules\$mod"
    New-Item -ItemType Directory -Force -Path $path | Out-Null
    $content = "# NEXUS AI Module: $mod`n# Implemented in later phases. See implementation_plan.md`n"
    Set-Content -Path "$path\__init__.py" -Value $content -Encoding UTF8
    Write-Host "Created: $path"
}

# Create all required directories
$allDirs = @(
    "data\cache\yfinance",
    "data\raw",
    "data\processed",
    "data\feature_store",
    "data\schemas",
    "streaming\producers",
    "streaming\consumers",
    "streaming\topics",
    "ml\training",
    "ml\evaluation",
    "ml\registry",
    "ml\notebooks",
    "docs\architecture",
    "docs\api",
    "docs\deployment",
    "docs\models",
    "backend\app\api\v1\endpoints",
    "backend\app\core",
    "backend\app\models",
    "backend\app\services",
    "backend\tests",
    "logs",
    "infrastructure\docker\postgres",
    "infrastructure\kubernetes"
)

foreach ($d in $allDirs) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}

# Create Python __init__.py files for all packages
$pyPkgs = @(
    "backend\app\__init__.py",
    "backend\app\api\__init__.py",
    "backend\app\api\v1\__init__.py",
    "backend\app\api\v1\endpoints\__init__.py",
    "backend\app\core\__init__.py",
    "backend\app\models\__init__.py",
    "backend\app\services\__init__.py",
    "backend\tests\__init__.py",
    "modules\__init__.py",
    "streaming\__init__.py",
    "streaming\producers\__init__.py",
    "streaming\consumers\__init__.py"
)

foreach ($f in $pyPkgs) {
    if (-not (Test-Path $f)) {
        Set-Content -Path $f -Value "" -Encoding UTF8
    }
}

# Create .gitkeep files for empty data directories
$keepDirs = @(
    "data\cache\yfinance",
    "data\raw",
    "data\processed",
    "data\feature_store",
    "ml\registry",
    "logs"
)

foreach ($d in $keepDirs) {
    Set-Content -Path "$d\.gitkeep" -Value "" -Encoding UTF8
}

Write-Host ""
Write-Host "All directories and stub files created successfully!"
