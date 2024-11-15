import firebase_admin
from firebase_admin import credentials, db
from tabulate import tabulate

# Firebase’ga ulanish
cred = credentials.Certificate("./pdp-projectquiz-firebase-adminsdk-a0msr-34c1ab9e5e.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://pdp-projectquiz.firebaseio.com'
})

def get_scores():
    try:
        scores_ref = db.reference('scores')
        all_data = scores_ref.get()
        sorted_data = sorted(all_data.items(), key=lambda x: x[1], reverse=True)
        table_data = [["Username", "Score"]]
        for username, score in sorted_data:
            table_data.append([username, score])

        print(tabulate(table_data, headers="firstrow", tablefmt="grid"))

    except Exception as e:
        print(f"Xatolik: {e}")

get_scores()
