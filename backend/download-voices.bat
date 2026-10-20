@echo off
REM Download free, offline Piper TTS voices into backend\voices (Windows).
REM Browse all voices: https://huggingface.co/rhasspy/piper-voices/tree/main
setlocal
cd /d "%~dp0voices"
set BASE=https://huggingface.co/rhasspy/piper-voices/resolve/main

for %%V in (
  "en/en_US/amy/low/en_US-amy-low"
  "en/en_US/lessac/low/en_US-lessac-low"
) do (
  for %%E in (onnx onnx.json) do (
    if not exist "%%~nxV.%%E" (
      echo Downloading %%~nxV.%%E ...
      curl -L --fail -o "%%~nxV.%%E" "%BASE%/%%~V.%%E"
    )
  )
)
echo Done. Restart the backend; voices appear automatically in the Storyboard.
endlocal
