import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from security.sanitizer import SecuritySanitizer


sanitizer = SecuritySanitizer()


test_data = {
    "internal_ip": "192.168.50.1",

    "windows_path":
        r"D:\Agentic_AI\data.json",

    "mac_path":
        "/Users/example/Agentic_AI/data.json",

    "network_share":
        r"\\server\share_files\jobs\test.json",

    "authorization":
        "Authorization: Bearer ABC123XYZ",

    "api_key":
        "api_key=SUPERSECRET123",

    "password":
        "password=my_password",

    "financial_data": {
        "ticker": "NVDA",
        "price": 195.50,
        "confidence": 0.91
    }
}


result = sanitizer.sanitize(
    test_data
)


print(result)