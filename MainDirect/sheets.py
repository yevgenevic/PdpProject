import gspread_asyncio
from oauth2client.service_account import ServiceAccountCredentials

SPREADSHEET_ID = '1n-2xd1BOjZdg3kuy2pdg0t_MTyjJ87BV5Gomk3Xsje0'
SHEET_NAME = 'PDP'


def auth_gspread():
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        '/home/yevgenevic/PycharmProjects/PdpProject/MainDirect/botproject-400713-67dc83c63c0d.json', scope)
    return creds


async def connect_to_google_sheets():
    agcm = gspread_asyncio.AsyncioGspreadClientManager(auth_gspread)
    agc = await agcm.authorize()
    sh = await agc.open_by_key(SPREADSHEET_ID)
    return await sh.worksheet(SHEET_NAME)


async def update_google_sheet(username, correct_count):
    try:
        sheet = await connect_to_google_sheets()
        cell = await sheet.find(username)

        if cell:
            current_count_value = await sheet.cell(cell.row, cell.col + 1)
            current_count = 0
            if current_count_value.value:
                current_count = int(current_count_value.value)
            await sheet.update_cell(cell.row, cell.col + 1, current_count + correct_count)
        else:
            await sheet.append_row([username, correct_count])

        all_data = await sheet.get_all_values()
        sorted_data = sorted(
            [row for row in all_data[1:] if row[1].isdigit()],
            key=lambda x: int(x[1]),
            reverse=True
        )
        await sheet.clear()
        await sheet.append_row(['Username', 'Score'])
        for row in sorted_data:
            await sheet.append_row(row)
    except Exception as e:
        print(f"An error occurred: {e}")
