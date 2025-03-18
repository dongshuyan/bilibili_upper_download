import asyncio
import argparse
import subprocess
from bilibili_api import user, sync
import os
import toml
import os

def read_toml_config(file_path: str = os.path.join(os.getcwd(), "config.toml")) -> dict:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            config_data = toml.load(f)
        return config_data
    except FileNotFoundError:
        print(f"Error: Config file not found at {file_path}")
        raise
    except toml.TomlDecodeError as e:
        print(f"Error: Invalid TOML format in {file_path}: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error reading {file_path}: {e}")
        raise

async def get_video_info(bvid: str, SESSDATA: str, BILI_JCT: str, BUVID3: str) -> dict:
    from bilibili_api import video, Credential
    credential = Credential(sessdata=SESSDATA, bili_jct=BILI_JCT, buvid3=BUVID3)
    v = video.Video(bvid=bvid, credential=credential)
    info = await v.get_info()
    return info

async def get_user_name(uid: int) -> str:
    u = user.User(uid)
    user_info = sync(u.get_user_info())
    return user_info["name"]

async def get_user_video_urls(uid: int) -> list:
    """获取指定用户的所有视频URL"""
    u = user.User(uid=uid)
    page = 1
    video_urls = []
    
    while True:
        try:
            res = await u.get_videos(pn=page)
            if not res["list"]["vlist"]:
                break
            for video_item in res["list"]["vlist"]:
                url = f"https://www.bilibili.com/video/{video_item['bvid']}"
                video_urls.append(url)
            page += 1
        except Exception as e:
            print(f"Error fetching video list page {page}: {e}")
            break
    
    return video_urls

def download_video(url: str, output_dir: str, quality: str, sessdata: str, timeout: int):
    """使用yutto下载单个视频（支持超时）"""
    command = [
        "yutto",
        "--sessdata", sessdata,
        "-d", output_dir,
        "-q", quality,
        url
    ]
    subprocess.run(command, check=True, timeout=timeout)
    print(f"Successfully downloaded: {url}")

async def download_all_videos(arg_dict: dict):
    uid = arg_dict["uid"]
    output_dir = arg_dict["output_dir"]
    quality = arg_dict["video_quality"]

    up_name = await get_user_name(uid)
    output_dir = os.path.join(output_dir, up_name)
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Fetching video list for UID: {uid}")
    video_urls = await get_user_video_urls(uid)
    
    if not video_urls:
        print("No videos found for this user.")
        return
    
    print(f"Found {len(video_urls)} videos to download")

    log_file = os.path.join(os.path.dirname(__file__), "download_errors.log")

    for i, url in enumerate(video_urls, 1):
        bvid = url.split("/")[-1]
        video_info = await get_video_info(
            bvid=bvid,
            SESSDATA=arg_dict["SESSDATA"],
            BILI_JCT=arg_dict["BILI_JCT"],
            BUVID3=arg_dict["BUVID3"]
        )
        print(f"Downloading video {i}/{len(video_urls)}")
        duration = video_info["duration"]
        print(f"视频名称：{video_info['title']}，视频时长：{duration}秒")

        # 根据视频时长设置超时（可按需调整系数）
        estimated_time = 5 + duration * 2
        max_attempts = 5
        success = False
        attempt = 0

        while attempt < max_attempts and not success:
            attempt += 1
            try:
                print(f"Download attempt #{attempt}")
                download_video(url, output_dir, quality, arg_dict["SESSDATA"], timeout=estimated_time)
                success = True
            except subprocess.TimeoutExpired:
                print(f"Timeout for {url}, will retry...")
            except subprocess.CalledProcessError as e:
                print(f"Error downloading {url}: {e}, will retry...")
            except Exception as e:
                print(f"Unexpected error downloading {url}: {e}, will retry...")

        if not success:
            # 记录到log
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(f"Failed to download {url} after {max_attempts} attempts.\n")

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="Download all videos from a Bilibili user"
    )
    parser.add_argument(
        "-u", "--uid",
        type=int,
        required=True,
        help="Bilibili user UID"
    )
    parser.add_argument(
        "-o", "--output_dir",
        type=str,
        required=False,
        help="Output directory for downloaded videos"
    )
    parser.add_argument(
        "-q", "--video_quality",
        type=str,
        default="127",
        choices=["127","126","125","120","116","112","100",
                 "80","74","64","32","16"],
        help="Video quality (default: 127 - 8K)"
    )
    return parser.parse_args()

def main():
    arg_dict = {
        "uid": 0,
        "output_dir": "~/Downloads",
        "video_quality": "",
        "SESSDATA": "",
        "BILI_JCT": "",
        "BUVID3": "",
    }
    """程序入口"""

    toml_args = read_toml_config()
    args = parse_arguments()
    args = vars(args)

    for key in arg_dict:
        if key in toml_args["basic"] and toml_args["basic"][key] != "" and toml_args["basic"][key] is not None:
            arg_dict[key] = toml_args["basic"][key]

    for key in arg_dict:
        if key in args and args[key] != "" and args[key] is not None:
            arg_dict[key] = args[key]

    asyncio.run(download_all_videos(arg_dict))

if __name__ == "__main__":
    main()