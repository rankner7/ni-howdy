"""Download and verify the optional local Taiwan Mandarin voice."""
import hashlib
from pathlib import Path
from urllib.request import urlopen

root = Path(__file__).resolve().parent.parent
target = root / '.data/models/primetts.onnx'
expected = '0cf64ad010a9b92201222533900ece31562a0181e7a8e435e5de83b3d72b4bdf'
if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
    print('Local Taiwan Mandarin voice is already installed.')
else:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.download')
    print('Downloading PrimeTTS v2.1 (about 112 MiB)…')
    with urlopen('https://huggingface.co/Luigi/PrimeTTS/resolve/7c47a46121d7006b2fc3cf7c49349fe5a86a9c5d/v21_mbistft_16k/primetts_v21_3voice.onnx', timeout=120) as response, temporary.open('wb') as out:
        while chunk := response.read(1024*1024):
            out.write(chunk)
    if hashlib.sha256(temporary.read_bytes()).hexdigest() != expected:
        temporary.unlink()
        raise SystemExit('Model checksum changed. The downloaded model was not installed.')
    temporary.replace(target)
    print('Local voice installed. Audio will be generated and cached on this machine.')
