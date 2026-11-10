# -*- coding: utf-8 -*-
"""
UYAP Tahliye Kontrol Robotu - OCR Metin Tanıma Motoru
Windows yerel Windows.Media.Ocr API'si ile çalışır (Tesseract gerekmez).
"""
import os
import re
import json
import subprocess
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PS1_SCRIPT = os.path.join(BASE_DIR, "win_ocr.ps1")

class OcrEngine:
    def __init__(self):
        self._ensure_ps1_script()

    def _ensure_ps1_script(self):
        if not os.path.exists(PS1_SCRIPT):
            ps1_code = r'''
param([string]$ImagePath)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
Add-Type -AssemblyName System.IO
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
[Windows.Globalization.Language, Windows.Globalization, ContentType=WindowsRuntime] | Out-Null

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
Function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    return $netTask.Result
}

$fullPath = [System.IO.Path]::GetFullPath($ImagePath)
if (-not (Test-Path $fullPath)) {
    @{ text = ""; lines = @() } | ConvertTo-Json -Depth 5 -Compress
    exit
}

$fs = [System.IO.File]::OpenRead($fullPath)
try {
    $ras = [System.IO.WindowsRuntimeStreamExtensions]::AsRandomAccessStream($fs)
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($ras)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])

    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    if ($null -eq $engine) {
        $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new("tr-TR"))
    }
    if ($null -eq $engine) {
        $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new("en-US"))
    }
    if ($null -eq $engine) {
        @{ text = ""; lines = @() } | ConvertTo-Json -Depth 5 -Compress
        exit
    }

    $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])

    $lines = @()
    foreach ($l in $result.Lines) {
        $words = @()
        foreach ($w in $l.Words) {
            $words += @{
                text = $w.Text
                x = [int]$w.BoundingRect.X
                y = [int]$w.BoundingRect.Y
                w = [int]$w.BoundingRect.Width
                h = [int]$w.BoundingRect.Height
            }
        }
        $lines += @{ text = $l.Text; words = $words }
    }

    @{ text = $result.Text; lines = $lines } | ConvertTo-Json -Depth 5 -Compress
}
finally {
    $fs.Dispose()
}
'''
            with open(PS1_SCRIPT, "w", encoding="utf-8") as f:
                f.write(ps1_code.strip())

    def run_ocr(self, image_path):
        """PowerShell Windows.Media.Ocr ile görseldeki tüm metinleri ve koordinatları çeker."""
        if not os.path.exists(image_path):
            return {"text": "", "lines": []}
        try:
            cmd = f'powershell -NoProfile -ExecutionPolicy Bypass -File "{PS1_SCRIPT}" -ImagePath "{image_path}"'
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="ignore")
            if proc.returncode == 0 and proc.stdout.strip():
                return json.loads(proc.stdout.strip())
        except Exception:
            pass
        return {"text": "", "lines": []}

    def recognize(self, image_path):
        return self.run_ocr(image_path)

    def recognize_pil_image(self, pil_image, upscale=True):
        tmp_path = os.path.join(BASE_DIR, "_temp_ocr.png")
        scale = 1.0
        try:
            # Küçük görsellerde ve kırpmalarda (crops) metin fontları 6-10 piksele kadar düşebilir.
            # Windows.Media.Ocr'ın küçük fontları eksiksiz okuması için en boy oranını koruyarak büyütürüz.
            img_to_save = pil_image
            if upscale:
                w, h = pil_image.size
                if w < 1600 or h < 900:
                    scale = 2.0 if (w > 800 or h > 450) else 2.5
                    img_to_save = pil_image.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

            img_to_save.save(tmp_path)
            data = self.run_ocr(tmp_path)
            data["scale"] = scale
            return data
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    @staticmethod
    def normalize_text(text):
        if not text:
            return ""
        t = text.lower()
        t = t.replace('ı', 'i').replace('İ', 'i').replace('ş', 's').replace('Ş', 's')
        t = t.replace('ğ', 'g').replace('Ğ', 'g').replace('ü', 'u').replace('Ü', 'u')
        t = t.replace('ö', 'o').replace('Ö', 'o').replace('ç', 'c').replace('Ç', 'c')
        t = re.sub(r'[^a-z0-9/.\s]', '', t)
        return " ".join(t.split())

    def contains_keywords(self, pil_image, keywords):
        """Görselde verilen anahtar kelimelerden en az biri geçiyor mu kontrol eder."""
        data = self.recognize_pil_image(pil_image)
        full_text = self.normalize_text(data.get("text", ""))
        for kw in keywords:
            if self.normalize_text(kw) in full_text:
                return True
        return False
