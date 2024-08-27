import sqlite3

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()


# 数据库连接函数
def get_db_connection():
    conn = sqlite3.connect('websites.db')
    conn.row_factory = sqlite3.Row  # 让查询结果返回字典格式
    return conn


# 定义一个显示页面的路由
@app.get("/", response_class=HTMLResponse)
async def read_websites():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 查询并根据 theme 分组
    cursor.execute("SELECT theme, url, title FROM c_website ORDER BY theme")
    websites = cursor.fetchall()
    conn.close()

    # 生成 HTML 内容
    html_content = """
    <html>
    <head>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }
            h1 {
                color: #333;
                text-align: center;
            }
            h2 {
                color: #666;
                margin-top: 30px;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
            }
            th, td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }
            th {
                background-color: #f2f2f2;
            }
            a {
                color: #0066cc;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <h1>网站列表</h1>
    """

    current_theme = None
    for website in websites:
        if website['theme'] != current_theme:
            if current_theme is not None:
                html_content += "</table>"
            current_theme = website['theme']
            html_content += f"<h2>{current_theme}</h2>"
            html_content += """
            <table>
                <tr>
                    <th width='50%'>链接</th>
                    <th width='50%'>标题</th>
                </tr>
            """

        html_content += f"""
        <tr>
            <td><a href='{website['url']}'>{website['url']}</a></td>
            <td>{website['title']}</td>
        </tr>
        """

    if current_theme is not None:
        html_content += "</table>"

    html_content += """
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
