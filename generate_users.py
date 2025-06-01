from faker import Faker
import random
import string

fake = Faker()

def generate_password_placeholder(length=60):
    chars = string.ascii_letters + string.digits + './$'
    return ''.join(random.choice(chars) for _ in range(length))

users = []
for _ in range(100):
    name = fake.name().replace("'", "''")  # Escape single quotes for SQL
    email = fake.unique.email().replace("'", "''")
    password = generate_password_placeholder()
    users.append(f"('{name}', '{email}', '{password}')")

sql = "INSERT INTO users (name, email, password) VALUES\n" + ",\n".join(users) + ";"

print(sql)
