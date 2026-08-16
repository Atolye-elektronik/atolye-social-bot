# Trendyol'da fotografi eksik urunleri listeler.
# Bu makinede Python kurulu olmadigi icin Python'suz calisan surum.
# (Ayni isi src/marketplaces/trendyol_missing_images.py de yapar — CI icin o kullanilir.)
#
# Kullanim:
#   powershell -ExecutionPolicy Bypass -File tools\trendyol_eksik_foto.ps1
#   powershell -ExecutionPolicy Bypass -File tools\trendyol_eksik_foto.ps1 -MinImages 4 -CheckLinks
#
# Kimlik bilgileri repo kokundeki .env dosyasindan okunur:
#   TRENDYOL_SUPPLIER_ID=...
#   TRENDYOL_API_KEY=...
#   TRENDYOL_API_SECRET=...

param(
    [int]$MinImages = 3,
    [switch]$CheckLinks,
    [switch]$IncludeArchived
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

# --- .env oku ---
$envPath = Join-Path $root '.env'
if (Test-Path $envPath) {
    foreach ($line in Get-Content $envPath) {
        $line = $line.Trim()
        if (-not $line -or $line.StartsWith('#') -or $line -notmatch '=') { continue }
        $k, $v = $line -split '=', 2
        Set-Item -Path "env:$($k.Trim())" -Value $v.Trim()
    }
}

$supplierId = $env:TRENDYOL_SUPPLIER_ID
$apiKey     = $env:TRENDYOL_API_KEY
$apiSecret  = $env:TRENDYOL_API_SECRET

$missing = @()
if (-not $supplierId) { $missing += 'TRENDYOL_SUPPLIER_ID' }
if (-not $apiKey)     { $missing += 'TRENDYOL_API_KEY' }
if (-not $apiSecret)  { $missing += 'TRENDYOL_API_SECRET' }
if ($missing.Count -gt 0) {
    Write-Host "Eksik ortam degiskeni: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "Repo kokune .env dosyasi olustur (Trendyol panelinde: Hesabim > Entegrasyon Bilgileri)."
    exit 1
}

$token = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("$apiKey`:$apiSecret"))
$headers = @{
    Authorization = "Basic $token"
    'User-Agent'  = "$supplierId - SelfIntegration"
}

$base = "https://apigw.trendyol.com/integration/product/sellers/$supplierId"

function Get-ProductPage($pageNo) {
    # V2 once (V1 filtreleme 10 Agustos 2026'da kapatildi), olmazsa V1'e dus.
    if ($script:ApiVersion -ne 'v1') {
        try {
            return Invoke-RestMethod -Uri "$base/products/approved?page=$pageNo&size=100" `
                -Headers $headers -Method Get -TimeoutSec 60
        } catch {
            $code = $null
            if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
            if ($script:ApiVersion -eq 'v2' -or $code -notin 400, 404, 410) { throw }
            Write-Host "V2 endpoint yanit vermedi (HTTP $code), V1'e dusuluyor..." -ForegroundColor Yellow
            $script:ApiVersion = 'v1'
        }
    }
    return Invoke-RestMethod -Uri "$base/products?page=$pageNo&size=100" `
        -Headers $headers -Method Get -TimeoutSec 60
}

# --- Tum ilanlari sayfa sayfa cek ---
$script:ApiVersion = $null
$all = New-Object System.Collections.ArrayList
$page = 0
do {
    Write-Host "Sayfa $page cekiliyor..." -ForegroundColor DarkGray
    $resp = Get-ProductPage $page
    if (-not $script:ApiVersion) { $script:ApiVersion = 'v2' }

    foreach ($p in $resp.content) { [void]$all.Add($p) }
    $totalPages = [int]$resp.totalPages
    $page++
} while ($page -lt $totalPages)

Write-Host "Toplam $($all.Count) ilan cekildi (API: $($script:ApiVersion)).`n" -ForegroundColor Cyan

# --- Siniflandir ---
$rows = New-Object System.Collections.ArrayList
foreach ($p in $all) {
    if (-not $IncludeArchived -and $p.archived -eq $true) { continue }

    $urls = @()
    foreach ($img in $p.images) {
        if ($img -is [string]) { $urls += $img }
        elseif ($img.url)      { $urls += $img.url }
        elseif ($img.imageUrl) { $urls += $img.imageUrl }
    }

    # V2'de barkod/stok kodu varyant seviyesinde, V1'de ilan seviyesinde.
    $variants = @($p.variants)
    if ($variants.Count -gt 0) {
        $barkodlar = @($variants | ForEach-Object { $_.barcode } | Where-Object { $_ })
        $stokKodlari = @($variants | ForEach-Object { $_.stockCode } | Where-Object { $_ })
        $stok = ($variants | ForEach-Object { [int]$_.stock.quantity } | Measure-Object -Sum).Sum
        $fiyat = $variants[0].price.salePrice
    } else {
        $barkodlar = @($p.barcode) | Where-Object { $_ }
        $stokKodlari = @($p.stockCode) | Where-Object { $_ }
        $stok = $p.quantity
        $fiyat = $p.salePrice
    }

    $durum = $null
    if ($urls.Count -eq 0)              { $durum = 'FOTOGRAF YOK' }
    elseif ($urls.Count -lt $MinImages) { $durum = 'AZ FOTOGRAF' }

    $bozuk = @()
    if ($CheckLinks -and $urls.Count -gt 0) {
        foreach ($u in $urls) {
            try {
                $r = Invoke-WebRequest -Uri $u -Method Head -TimeoutSec 15 -UseBasicParsing
                if ([int]$r.StatusCode -ge 400) { $bozuk += $u }
            } catch { $bozuk += $u }
        }
        if ($bozuk.Count -gt 0 -and -not $durum) { $durum = 'KIRIK LINK' }
    }

    if ($durum) {
        [void]$rows.Add([pscustomobject]@{
            Durum        = $durum
            ContentId    = $p.contentId
            Urun         = $p.title
            Marka        = $p.brand
            Barkodlar    = ($barkodlar -join ' | ')
            StokKodlari  = ($stokKodlari -join ' | ')
            GorselSayisi = $urls.Count
            Stok         = $stok
            Fiyat        = $fiyat
            KirikLinkler = ($bozuk -join ' | ')
            Gorseller    = ($urls -join ' | ')
        })
    }
}

# --- Rapor ---
$raporDir = Join-Path $root 'raporlar'
if (-not (Test-Path $raporDir)) { New-Item -ItemType Directory -Path $raporDir | Out-Null }
$csvPath  = Join-Path $raporDir 'trendyol_eksik_gorseller.csv'
$jsonPath = Join-Path $root 'state\trendyol_eksik_gorseller.json'

$rows | Sort-Object Durum, GorselSayisi | Export-Csv -Path $csvPath -NoTypeInformation -Encoding UTF8
$rows | ConvertTo-Json -Depth 5 | Out-File -FilePath $jsonPath -Encoding utf8

$yok = @($rows | Where-Object { $_.Durum -eq 'FOTOGRAF YOK' })
$az  = @($rows | Where-Object { $_.Durum -eq 'AZ FOTOGRAF' })
$kir = @($rows | Where-Object { $_.Durum -eq 'KIRIK LINK' })

Write-Host "Fotografi hic olmayan : $($yok.Count)" -ForegroundColor Red
Write-Host "Fotografi yetersiz    : $($az.Count) (esik: $MinImages)" -ForegroundColor Yellow
if ($CheckLinks) { Write-Host "Kirik gorsel linki    : $($kir.Count)" -ForegroundColor Yellow }
Write-Host ""

$rows | Sort-Object Durum, GorselSayisi |
    Format-Table Durum, ContentId, Barkodlar, GorselSayisi, Stok, Urun -AutoSize

Write-Host "`nCSV : $csvPath"
Write-Host "JSON: $jsonPath"
