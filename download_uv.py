# 下载 uv.exe
import requests
import zipfile
import os

def download_uv():
    url = "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip"
    print(f"正在下载 uv.exe...")
    print(f"地址: {url}")

    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()

        with open("uv.zip", "wb") as f:
            f.write(response.content)

        print("✅ 下载完成，正在解压...")

        with zipfile.ZipFile("uv.zip") as z:
            z.extract("uv.exe")

        os.remove("uv.zip")
        print("✅ uv.exe 准备完成！")
        return True
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        return False

if __name__ == "__main__":
    download_uv()
