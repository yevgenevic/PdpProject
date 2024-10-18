import gspread
from oauth2client.service_account import ServiceAccountCredentials

SPREADSHEET_ID = '1n-2xd1BOjZdg3kuy2pdg0t_MTyjJ87BV5Gomk3Xsje0'
SHEET_NAME = 'PDP'


def connect_to_google_sheets():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    credentials = ServiceAccountCredentials.from_json_keyfile_name('botproject-400713-67dc83c63c0d.json', scope)
    gc = gspread.authorize(credentials)
    print(f"Opening spreadsheet with ID: {SPREADSHEET_ID}")
    return gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)


def update_google_sheet(username, correct_count):
    sheet = connect_to_google_sheets()
    try:
        cell = sheet.find(username)
        if cell:
            current_count = int(sheet.cell(cell.row, cell.col + 1).value)
            sheet.update_cell(cell.row, cell.col + 1, current_count + correct_count)
        else:
            sheet.append_row([username, correct_count])
        sheet.sort((2, 'des'))
    except gspread.exceptions.WorksheetNotFound:
        print(f"Worksheet with name not found.")
    except Exception as e:
        print(f"An error occurred: {e}")
