from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
import markdown
import sqlite3
import zipfile
import io
import re
import os
import datetime
from bs4 import BeautifulSoup

app = Flask(__name__)

# --- DB 初期化 ---
def init_db():
    conn = sqlite3.connect("articles.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            image TEXT,
            author TEXT,
            content TEXT
        )
    """)
    conn.commit()
    conn.close()

# --- 記事一覧 ---
@app.route("/")
def index():
    conn = sqlite3.connect("articles.db")
    c = conn.cursor()
    c.execute("SELECT id, title FROM articles")
    articles = c.fetchall()
    conn.close()
    return render_template("index.html", articles=articles)

# --- 記事作成 ---
@app.route("/new", methods=["GET", "POST"])
def new_article():
    if request.method == "POST":
        title = request.form["title"]
        author = request.form["author"]
        content = request.form["content"]

        # ファイルアップロード処理
        image_file = request.files.get("image")
        image_path = None
        if image_file and image_file.filename:
            # static/uploads フォルダに保存
            upload_dir = os.path.join(app.root_path, "static", "uploads")
            os.makedirs(upload_dir, exist_ok=True)
            filepath = os.path.join(upload_dir, image_file.filename)
            image_file.save(filepath)

            # DBに保存するパスはブラウザからアクセスできるURL形式
            image_path = url_for("static", filename=f"uploads/{image_file.filename}")

        conn = sqlite3.connect("articles.db")
        c = conn.cursor()
        c.execute(
            "INSERT INTO articles (title, author, image, content) VALUES (?, ?, ?, ?)",
            (title, author, image_path, content)
        )
        conn.commit()
        conn.close()

        return redirect(url_for("index"))

    return render_template("new.html")


# --- 記事詳細 ---
@app.route("/article/<int:id>")
def article(id):
    conn = sqlite3.connect("articles.db")
    c = conn.cursor()
    c.execute("SELECT title, content FROM articles WHERE id=?", (id,))
    row = c.fetchone()
    conn.close()

    if row:
        title, content = row
        html = markdown.markdown(content)
        return render_template("article.html", id=id, title=title, html=html)
    else:
        return "記事が見つかりません", 404


@app.route("/delete/<int:id>", methods=["POST"])
def delete_article(id):
    conn = sqlite3.connect("articles.db")
    c = conn.cursor()
    c.execute("DELETE FROM articles WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

@app.route("/export/<int:id>")
def export_article(id):
    conn = sqlite3.connect("articles.db")
    c = conn.cursor()
    c.execute("SELECT title, author, image, content FROM articles WHERE id=?", (id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return "記事が見つかりません", 404

    title, author, image, content = row

    # フロントマター付き Markdown
    md_content = f"""---
title: "{title}"
image: "{image or ''}"
author: "{author or ''}"
date: "{datetime.date.today().isoformat()}"
---

{content}
"""

    # 画像パス抽出（Markdown と HTML 両方）
    image_paths = []

    # Markdown形式 ![...](...)
    import re
    image_paths += re.findall(r'!\[.*?\]\((.*?)\)', content)

    # HTML形式 <img src="..."> を BeautifulSoup で抽出
    soup = BeautifulSoup(content, "html.parser")
    for img_tag in soup.find_all("img"):
        src = img_tag.get("src")
        if src:
            image_paths.append(src)

    # フロントマターの image も追加
    if image and image.strip():
        image_paths.append(image)

    # 重複を削除
    image_paths = list(set(image_paths))

    # ファイル名用に安全化
    safe_title = re.sub(r'[\\/*?:"<>|]', "_", title)
    safe_author = author if author else "export"
    image_folder = f"{safe_title}_images"

    # ZIP作成（メモリ上）
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr(f"{safe_title}.md", md_content)

        # 画像追加
        for img_path in image_paths:
            if os.path.exists(img_path):
                zf.write(img_path, os.path.join(image_folder, os.path.basename(img_path)))

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        as_attachment=True,
        download_name=f"{safe_author}.zip",
        mimetype="application/zip"
    )


@app.route("/upload_image", methods=["POST"])
def upload_image():
    file = request.files.get("image")
    if not file:
        return {"error": "No file"}, 400

    os.makedirs("static/uploads", exist_ok=True)
    filepath = os.path.join("static/uploads", file.filename)
    file.save(filepath)

    url = url_for("static", filename=f"uploads/{file.filename}")
    return {"url": url}

@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_article(id):
    conn = sqlite3.connect("articles.db")
    c = conn.cursor()
    c.execute("SELECT title, author, image, content FROM articles WHERE id=?", (id,))
    row = c.fetchone()

    if not row:
        conn.close()
        return "記事が見つかりません", 404

    title, author, image, content = row

    if request.method == "POST":
        new_title = request.form["title"]
        new_author = request.form["author"]
        new_content = request.form["content"]

        image_file = request.files.get("image")
        if image_file and image_file.filename:
            os.makedirs("static/uploads", exist_ok=True)
            image_path = os.path.join("static/uploads", image_file.filename)
            image_file.save(image_path)
        else:
            image_path = image

        c.execute(
            "UPDATE articles SET title=?, author=?, image=?, content=? WHERE id=?",
            (new_title, new_author, image_path, new_content, id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("article", id=id))

    conn.close()
    return render_template("edit.html", id=id, title=title, author=author, image=image, content=content)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
