import firebase_admin
from firebase_admin import credentials, db


cred = credentials.Certificate("./pdp-projectquiz-firebase-adminsdk-a0msr-34c1ab9e5e.json")  
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://your-database-name.firebaseio.com'  
})



async def update_firebase_score(username, correct_count):
    try:
        user_ref = db.reference(f'scores/{username}')
        current_score = user_ref.get() or 0
        user_ref.set(current_score + correct_count)
        scores_ref = db.reference('scores')
        all_data = scores_ref.get()
        sorted_data = sorted(all_data.items(), key=lambda x: x[1], reverse=True)
        
        print("Reyting:")
        for username, score in sorted_data:
            print(f"{username}: {score}")

    except Exception as e:
        print(f"An error occurred: {e}")
