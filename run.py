from app import create_app, db

app = create_app()

# Ensure the database is created before running the app
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)



