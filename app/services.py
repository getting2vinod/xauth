import hmac
import hashlib
from pathlib import Path
from datetime import datetime
import gspread
from app.config import settings

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
CREDENTIALS_PATH = CONFIG_DIR / "myutils-437714-bd0d0a3e77bd.json"

def encrypt(txt: str) -> str:
    txt_bytes = txt.encode()
    skey = settings.PWD_HASH_KEY.encode()
    hmac_object = hmac.new(skey, txt_bytes, hashlib.sha256)
    return hmac_object.hexdigest()

def get_sheet():
    """
    Connects to Google Sheets API using service account credentials
    at the specified config path and opens the spreadsheet by URL or key/name.
    """
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(f"Service account file missing at '{CREDENTIALS_PATH}'.")

    gc = gspread.service_account(filename=str(CREDENTIALS_PATH))

    sheet_identifier = settings.GOOGLE_SHEET_NAME
    if sheet_identifier.startswith("http"):
        spreadsheet = gc.open_by_url(sheet_identifier)
    elif len(sheet_identifier) > 20 and not " " in sheet_identifier:
        spreadsheet = gc.open_by_key(sheet_identifier)
    else:
        try:
            spreadsheet = gc.open(sheet_identifier)
        except Exception:
            # Fallback if open by name fails and it's treated as a key
            spreadsheet = gc.open_by_key(sheet_identifier)

    return spreadsheet.sheet1

def get_username_from_token(token: str | None) -> str:
    """
    Looks up the provided token in the Google Sheet records.
    Returns the associated username if found, or falls back to 'default'.
    """
    if not token:
        return "default"
    
    try:
        sheet = get_sheet()
        records = sheet.get_all_records()
        
        for row in records:
            db_token = str(row.get("Token") or row.get("token") or "").strip()
            if db_token == token.strip():
                row_username = str(row.get("UserName") or row.get("username") or row.get("User") or "").strip()
                if row_username:
                    return row_username
                    
        return "default"
    except Exception as e:
        print(f"Error fetching username from token: {e}")
        return "default"

def verify_user(username: str, plain_password: str):
    sheet = get_sheet()
    records = sheet.get_all_records()
    
    for i, row in enumerate(records, start=2):
        row_username = str(row.get("UserName") or row.get("username") or row.get("User") or "").strip()
        if row_username.lower() == username.strip().lower():
            db_password = str(row.get("Password") or row.get("password") or "").strip()
            
            # If password field is blank -> trigger new password update screen
            if not db_password:
                return {"status": "update_required", "row": i, "username": username}
            
            hashed_input = encrypt(plain_password)
            if hmac.compare_digest(hashed_input, db_password):
                now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                try:
                    sheet.update_cell(i, 5, now)
                except Exception:
                    pass
                
                token = str(row.get("Token") or row.get("token") or "").strip()
                if not token:
                    token = encrypt(username + now)[:32]
                    try:
                        sheet.update_cell(i, 4, token)
                    except Exception:
                        pass
                    
                return {"status": "success", "token": token, "username": username}
            else:
                return {"status": "invalid_password"}
                
    return {"status": "user_not_found"}

def update_user_password(username: str, new_password: str, current_password: str | None = None):
    """
    Updates the user's password in Google Sheets.
    If `current_password` is provided, it verifies the current password before proceeding.
    """
    sheet = get_sheet()
    records = sheet.get_all_records()
    
    for i, row in enumerate(records, start=2):
        row_username = str(row.get("UserName") or row.get("username") or row.get("User") or "").strip()
        if row_username.lower() == username.strip().lower():
            db_password = str(row.get("Password") or row.get("password") or "").strip()

            # Verify current password if user already has a password set and current_password is given
            if db_password and current_password is not None:
                hashed_current = encrypt(current_password)
                if not hmac.compare_digest(hashed_current, db_password):
                    return {"status": "invalid_current_password"}
            
            hashed_password = encrypt(new_password)
            now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            
            # Update Password (Column 3) and LastLogin (Column 5)
            sheet.update_cell(i, 3, hashed_password)
            sheet.update_cell(i, 5, now)
            return {"status": "success"}
            
    return {"status": "user_not_found"}