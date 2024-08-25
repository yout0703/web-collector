from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import sqlite3

app = FastAPI()

# 数据库连接函数
def get_db_connection():
    conn = sqlite3.connect('src/web_collector/websites.db')
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
    html_content = "<html><body><h1>网站列表</h1>"

    current_theme = None
    for website in websites:
        if website['theme'] != current_theme:
            if current_theme is not None:
                html_content += "</ul>"
            current_theme = website['theme']
            html_content += f"<h2>{current_theme}</h2><ul>"

        html_content += f"<li>「{website['title']}」 => <a href='{website['url']}'>{website['url']} </a></li>"

    if current_theme is not None:
        html_content += "</ul>"

    html_content += "</body></html>"

    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
