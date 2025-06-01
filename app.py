import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "your_secret_key"

# MySQL configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'karthik'  # <-- Replace with your MySQL password
app.config['MYSQL_DB'] = 'college_marketplace'

mysql = MySQL(app)

# Image upload configuration
UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2 MB max
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def home():
    return render_template("home_new.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        hashed_password = generate_password_hash(password)
        cur = mysql.connection.cursor()
        try:
            cur.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", (name, email, hashed_password))
            mysql.connection.commit()
            cur.close()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            cur.close()
            flash(f"Error: {e}", "danger")
            return render_template("register.html")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()
        if user and check_password_hash(user[3], password):  # user[3] is the password column
            session['user_id'] = user[0]
            session['user_name'] = user[1]  # Make sure this is the correct column for name
            flash("Login successful!", "success")
            return redirect(url_for('home'))
        else:
            flash("Invalid email or password.", "danger")
            return render_template("login.html")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))

@app.route("/post_product", methods=["GET", "POST"])
def post_product():
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in to post a product.", "danger")
        return redirect(url_for('login'))

    if request.method == "POST":
        name = request.form["name"]
        category = request.form["category"]
        price = request.form["price"]
        description = request.form["description"]

        image_file = request.files.get("image")
        image_filename = None

        if image_file and allowed_file(image_file.filename):
            image_filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            image_file.save(image_path)
        elif image_file and image_file.filename != "":
            flash("Invalid image file type!", "danger")
            return render_template("post_product.html")

        cur = mysql.connection.cursor()
        try:
            cur.execute(
                "INSERT INTO products (name, category, price, description, user_id, image) VALUES (%s, %s, %s, %s, %s, %s)",
                (name, category, price, description, user_id, image_filename)
            )
            mysql.connection.commit()
            cur.close()
            flash("Product posted successfully!", "success")
            return redirect(url_for('post_product'))
        except Exception as e:
            cur.close()
            flash(f"Error: {e}", "danger")
            return render_template("post_product.html")
    return render_template("post_product.html")

@app.route("/products")
def products():
    user_id = session.get('user_id')
    q = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    min_price = request.args.get('min_price', '').strip()
    max_price = request.args.get('max_price', '').strip()

    query = """
        SELECT p.id, p.name, p.category, p.price, p.description, p.is_sold, u.name AS seller_name, p.image, p.user_id
        FROM products p
        JOIN users u ON p.user_id = u.id
        WHERE p.is_sold = FALSE
    """
    params = []

    if q:
        query += " AND p.name LIKE %s"
        params.append(f"%{q}%")
    if category:
        query += " AND p.category = %s"
        params.append(category)
    if min_price:
        query += " AND p.price >= %s"
        params.append(min_price)
    if max_price:
        query += " AND p.price <= %s"
        params.append(max_price)

    cur = mysql.connection.cursor()
    cur.execute(query, params)
    products = cur.fetchall()
    cur.close()
    return render_template(
        "products.html",
        products=products,
        q=q,
        category=category,
        min_price=min_price,
        max_price=max_price,
        user_id=user_id
    )

@app.route("/mark_sold/<int:product_id>", methods=["POST"])
def mark_sold(product_id):
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in to mark products as sold.", "danger")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT name, user_id FROM products WHERE id = %s", (product_id,))
    product = cur.fetchone()
    if product:
        product_name, owner_id = product
        if owner_id != user_id:
            flash("You can only mark your own products as sold.", "danger")
        else:
            cur.execute("UPDATE products SET is_sold = TRUE WHERE id = %s", (product_id,))
            mysql.connection.commit()
            flash(f'"{product_name}" is marked as sold!', "success")
    else:
        flash("Product not found.", "danger")
    cur.close()
    return redirect(url_for('products'))

@app.route("/add_to_wishlist/<int:product_id>", methods=["POST"])
def add_to_wishlist(product_id):
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in to add to wishlist.", "danger")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM wishlist WHERE user_id = %s AND product_id = %s", (user_id, product_id))
    exists = cur.fetchone()
    if exists:
        flash("Product is already in your wishlist.", "danger")
    else:
        cur.execute("INSERT INTO wishlist (user_id, product_id) VALUES (%s, %s)", (user_id, product_id))
        mysql.connection.commit()
        flash("Product added to your wishlist!", "success")
    cur.close()
    return redirect(url_for('products'))

@app.route("/wishlist")
def wishlist():
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in to view your wishlist.", "danger")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT p.name, p.category, p.price, p.description, p.image, p.id
        FROM products p
        JOIN wishlist w ON p.id = w.product_id
        WHERE w.user_id = %s AND p.is_sold = FALSE
    """, (user_id,))
    wishlist_items = cur.fetchall()
    total_price = sum([item[2] for item in wishlist_items]) if wishlist_items else 0
    cur.close()
    return render_template("wishlist.html", wishlist_items=wishlist_items, total_price=total_price)

@app.route("/order/<int:product_id>", methods=["GET", "POST"])
def order_product(product_id):
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in to place an order.", "danger")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name, price FROM products WHERE id = %s AND is_sold = FALSE", (product_id,))
    product = cur.fetchone()
    if not product:
        cur.close()
        flash("Product not found or already sold.", "danger")
        return redirect(url_for('products'))

    if request.method == "POST":
        order_type = request.form.get("order_type")
        cur.execute("INSERT INTO orders (user_id, total_price, order_type) VALUES (%s, %s, %s)",
                    (user_id, product[2], order_type))
        order_id = cur.lastrowid
        cur.execute("INSERT INTO order_items (order_id, product_id) VALUES (%s, %s)", (order_id, product_id))
        # Mark product as sold
        cur.execute("UPDATE products SET is_sold = TRUE WHERE id = %s", (product_id,))
        mysql.connection.commit()
        cur.close()
        flash("Order placed successfully!", "success")
        return redirect(url_for('products'))

    cur.close()
    return render_template("order.html", products=[product], total_price=product[2])

@app.route("/order_wishlist", methods=["GET", "POST"])
def order_wishlist():
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in to place an order.", "danger")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT p.id, p.name, p.price
        FROM products p
        JOIN wishlist w ON p.id = w.product_id
        WHERE w.user_id = %s AND p.is_sold = FALSE
    """, (user_id,))
    products = cur.fetchall()
    total_price = sum([p[2] for p in products]) if products else 0

    if request.method == "POST":
        order_type = request.form.get("order_type")
        cur.execute("INSERT INTO orders (user_id, total_price, order_type) VALUES (%s, %s, %s)",
                    (user_id, total_price, order_type))
        order_id = cur.lastrowid
        for p in products:
            cur.execute("INSERT INTO order_items (order_id, product_id) VALUES (%s, %s)", (order_id, p[0]))
            # Mark each product as sold
            cur.execute("UPDATE products SET is_sold = TRUE WHERE id = %s", (p[0],))
        mysql.connection.commit()
        cur.close()
        flash("Order placed successfully for your wishlist items!", "success")
        return redirect(url_for('products'))

    cur.close()
    return render_template("order.html", products=products, total_price=total_price)

@app.route("/my_orders")
def my_orders():
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in to view your orders.", "danger")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT o.id, o.created_at, o.total_price, o.order_type, o.status
        FROM orders o
        WHERE o.user_id = %s
        ORDER BY o.created_at DESC
    """, (user_id,))
    orders = cur.fetchall()

    # Fetch products for each order
    order_products = {}
    for order in orders:
        cur.execute("""
            SELECT p.name, p.price
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = %s
        """, (order[0],))
        order_products[order[0]] = cur.fetchall()
    cur.close()

    return render_template("my_orders.html", orders=orders, order_products=order_products)

@app.route("/profile")
def profile():
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in to view your profile.", "danger")
        return redirect(url_for('login'))

    # Fetch user's posted products
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT id, name, category, price, description, is_sold, image
        FROM products
        WHERE user_id = %s
        ORDER BY id DESC
    """, (user_id,))
    my_products = cur.fetchall()

    # Fetch user's wishlist products (not sold)
    cur.execute("""
        SELECT p.name, p.category, p.price, p.description, p.image, p.id
        FROM products p
        JOIN wishlist w ON p.id = w.product_id
        WHERE w.user_id = %s AND p.is_sold = FALSE
    """, (user_id,))
    wishlist_products = cur.fetchall()
    cur.close()

    return render_template("my_profile.html", my_products=my_products, wishlist_products=wishlist_products)

@app.route("/edit_product/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in to edit products.", "danger")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name, category, price, description, image FROM products WHERE id = %s AND user_id = %s", (product_id, user_id))
    product = cur.fetchone()

    if not product:
        cur.close()
        flash("Product not found or you do not have permission to edit.", "danger")
        return redirect(url_for('profile'))

    if request.method == "POST":
        name = request.form["name"]
        category = request.form["category"]
        price = request.form["price"]
        description = request.form["description"]

        # Handle image update
        image_file = request.files.get("image")
        image_filename = product[5]  # Keep old image by default

        if image_file and image_file.filename and allowed_file(image_file.filename):
            image_filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            image_file.save(image_path)
        elif image_file and image_file.filename != "":
            flash("Invalid image file type!", "danger")
            cur.close()
            return render_template("edit_product.html", product=product)

        cur.execute(
            "UPDATE products SET name=%s, category=%s, price=%s, description=%s, image=%s WHERE id=%s AND user_id=%s",
            (name, category, price, description, image_filename, product_id, user_id)
        )
        mysql.connection.commit()
        cur.close()
        flash("Product updated successfully!", "success")
        return redirect(url_for('profile'))

    cur.close()
    return render_template("edit_product.html", product=product)

@app.route("/delete_product/<int:product_id>", methods=["POST"])
def delete_product(product_id):
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in to delete products.", "danger")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT user_id, image FROM products WHERE id = %s", (product_id,))
    product = cur.fetchone()
    if not product or product[0] != user_id:
        cur.close()
        flash("Product not found or you do not have permission to delete.", "danger")
        return redirect(url_for('profile'))

    # 1. Delete from wishlist first (and any other referencing tables if needed)
    cur.execute("DELETE FROM wishlist WHERE product_id = %s", (product_id,))
    # Optionally, do the same for order_items if you want to allow deleting sold products:
    # cur.execute("DELETE FROM order_items WHERE product_id = %s", (product_id,))

    # 2. Optionally, delete the image file from the server
    image_filename = product[1]
    if image_filename:
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
        if os.path.exists(image_path):
            os.remove(image_path)

    # 3. Delete product from DB
    cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
    mysql.connection.commit()
    cur.close()
    flash("Product deleted successfully!", "success")
    return redirect(url_for('profile'))


if __name__ == "__main__":
    app.run(debug=True)

