import asyncio
import argparse
import subprocess
import csv
import os
from bilibili_api import user, sync
import toml
from pathlib import Path
from copy import deepcopy

import tempfile
import shutil

def extract_and_convert_time(input_str):
    # 提取字符串中的所有数字
    num_str = ''.join(char for char in input_str if char.isdigit())
    # 转换为整数（秒数）
    try:
        seconds = int(num_str)
    except ValueError:
        return "输入无效，无法提取数字"
    # 计算时间单位
    days = seconds // (24 * 3600)
    remaining_seconds = seconds % (24 * 3600)
    hours = remaining_seconds // 3600
    remaining_seconds %= 3600
    minutes = remaining_seconds // 60
    secs = remaining_seconds % 60
    # 构建结果字符串
    result = ""
    if days > 0:
        result += f"{days}d"
    if hours > 0 or days > 0:  # 即使hours为0，如果有天数也要显示
        result += f"{hours}h"
    if minutes > 0 or hours > 0 or days > 0:  # 即使minutes为0，如果有小时或天数也要显示
        result += f"{minutes}m"
    result += f"{secs}s"
    return result

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
    #credential = Credential(sessdata=SESSDATA, bili_jct=BILI_JCT, buvid3=BUVID3)
    credential = Credential(sessdata='', bili_jct='', buvid3='')
    v = video.Video(bvid=bvid, credential=credential)
    info = await v.get_info()
    return info

async def get_user_name(uid: int) -> str:
    u = user.User(uid)
    user_info = sync(u.get_user_info())
    return user_info["name"]

def get_file_names(output_dir: str, video_info: dict) -> list:
    """获取视频文件名"""
    filenames=[]
    title = video_info['title']
    if len( video_info['pages'])==1:
        return [os.path.join(output_dir, f"{title}.mp4")]
    # 如果有分P，添加P数
    for pages in video_info['pages']:
        filenames.append(os.path.join(output_dir, title, f"{pages['part']}.mp4")) 
    return filenames

async def get_user_video_urls(uid: int, output_dir: str, updatefile: bool = False) -> list:
    """获取指定用户的所有视频URL，并处理CSV文件"""
    csv_path = Path(output_dir) / "video_urls.csv"
    video_urls = []

    if csv_path.exists():
        print(f"Reading video URLs from {csv_path}")
        # 读取现有CSV文件
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            video_urls = list(reader)
        
        # 检查是否所有视频都已下载
        all_downloaded = all(v['downloaded'] == 'True' for v in video_urls)
        if all_downloaded and updatefile:
            # 询问用户是否需要更新
            update = input("All videos appear to be downloaded. Do you want to check for updates? (y/n): ")
            if update.lower() == 'y':
                # 重新抓取视频列表
                u = user.User(uid=uid)
                page = 1
                new_video_urls = []
                
                while True:
                    try:
                        res = await u.get_videos(pn=page)
                        if not res["list"]["vlist"]:
                            break
                        for video_item in res["list"]["vlist"]:
                            new_video_urls.append({
                                'url': f"https://www.bilibili.com/video/{video_item['bvid']}",
                                'title': '',
                                'duration': '',
                                'downloaded': 'False',
                                'file_path': ''
                            })
                        page += 1
                    except Exception as e:
                        print(f"Error fetching video list page {page}: {e}")
                        break
                
                # 找出新视频（不在原有列表中的URL）
                existing_urls = {v['url'] for v in video_urls}
                new_videos = [v for v in new_video_urls if v['url'] not in existing_urls]
                
                if new_videos:
                    video_urls.extend(new_videos)
                    print(f"Found {len(new_videos)} new videos to add to the list.")
                    save_to_csv(video_urls, csv_path)
                else:
                    print("No new videos found.")
        
        return video_urls

    # 如果没有CSV文件，获取视频列表
    u = user.User(uid=uid)
    page = 1
    
    while True:
        try:
            res = await u.get_videos(pn=page)
            if not res["list"]["vlist"]:
                break
            for video_item in res["list"]["vlist"]:
                video_urls.append({
                    'url': f"https://www.bilibili.com/video/{video_item['bvid']}",
                    'title': '',
                    'duration': '',
                    'downloaded': 'False',
                    'file_path': ''
                })
            page += 1
        except Exception as e:
            print(f"Error fetching video list page {page}: {e}")
            break
    
    # 保存初始CSV文件
    save_to_csv(video_urls, csv_path)
    return video_urls



def save_to_csv(video_urls: list, csv_path: Path):
    """保存视频信息到CSV文件"""
    video_urls_temp = deepcopy(video_urls)
    for item in video_urls_temp:
        for key in item:
            item[key] = str(item[key])
    fieldnames = ['url', 'title', 'duration', 'downloaded', 'file_path','info']
    # 创建临时文件
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='', delete=False) as temp_file:
        try:
            writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(video_urls_temp)
            temp_file.flush()  # 确保内容写入磁盘
            # 只有当写入成功时才替换原文件
            shutil.move(temp_file.name, csv_path)
        except Exception as e:
            # 如果发生错误，删除临时文件并抛出异常
            temp_file.close()
            Path(temp_file.name).unlink()
            raise e


def download_video(url: str, output_dir: str, quality: str, sessdata: str, video_info: dict, timeout: int) -> str:
    if timeout>600:
        timeout = 600
    """使用yutto下载单个视频并返回文件路径"""
    if (len(video_info['pages'])>1):
        command = [
            "yutto",
            "--sessdata", str(sessdata),
            "-d", str(output_dir),
            "-q", str(quality),
            "-b",
            "-p", "1~-1",
            "--download-interval", "2",
            "--save-cover",
            url
        ]
    else:
        command = [
            "yutto",
            "--sessdata", str(sessdata),
            "-d", str(output_dir),
            "-q", str(quality),
            "-p", "1~-1",
            "--download-interval", "2",
            "--save-cover",
            url
        ]
    subprocess.run(command, check=True, timeout=timeout)
    # 假设下载的文件名基于URL的bvid
    bvid = url.split("/")[-1]
    # file_path = os.path.join(output_dir, f"{title}.mp4")  # 可能需要根据实际情况调整
    filepaths = get_file_names(output_dir, video_info)
    print(f"Successfully downloaded: {url}")
    return filepaths

async def download_all_videos(arg_dict: dict, progress_callback=None):
    uid = arg_dict["uid"]
    output_dir = arg_dict["output_dir"]
    quality = arg_dict["video_quality"]

    up_name = await get_user_name(uid)
    output_dir = os.path.join(output_dir, up_name)
    os.makedirs(output_dir, exist_ok=True)

    if progress_callback:
        progress_callback(f"Fetching video list for UID: {uid} (UP: {up_name})\n")
    
    print(f"Fetching video list for UID: {uid}")
    video_urls = await get_user_video_urls(uid, output_dir, updatefile=True)
    
    csv_path = Path(output_dir) / "video_urls.csv"
    

    if not video_urls:
        print("No videos found for this user.")
        if progress_callback:
            progress_callback("No videos found for this user.\n")
        return
    
    total_videos = len(video_urls)

    if progress_callback:
        progress_callback(f"Found {total_videos} videos\n")
    
    print(f"Found {total_videos} videos")

    log_file = os.path.join(os.path.dirname(__file__), "download_errors.log")

    for i, video in enumerate(video_urls, 1):
        url = video['url']
        if video['downloaded'] == 'True':
            print(f"Skipping already downloaded video {i}/{total_videos}: {video['title']}")
            continue

        bvid = url.split("/")[-1]
        # video_info = await get_video_info(
        #     bvid=bvid,
        #     SESSDATA=arg_dict["SESSDATA"],
        #     BILI_JCT=arg_dict["BILI_JCT"],
        #     BUVID3=arg_dict["BUVID3"]
        # )
        video_info = await get_video_info(
            bvid=bvid,
            SESSDATA="",
            BILI_JCT="",
            BUVID3=""
        )
        
        # 更新视频信息
        video['title'] = video_info['title']
        # video['duration'] = str(video_info['duration'])
        video['duration'] = extract_and_convert_time(str(video_info['duration']))
        video['info'] = str(video_info)
        save_to_csv(video_urls, csv_path)

        print(f"Downloading video {i}/{total_videos}")
        print(f"视频名称：{video_info['title']}，视频时长：{video['duration']}")
        if progress_callback:
            progress_callback(f"Downloading video {i}/{total_videos}: {video_info['title']} (Duration: {video['duration']})\n")

        estimated_time = 5 + video_info['duration'] * 2
        max_attempts = 5
        success = False
        attempt = 0

        while attempt < max_attempts and not success:
            attempt += 1
            try:
                if progress_callback:
                    progress_callback(f"Attempt {attempt}/{max_attempts} for video {i}/{total_videos}\n")
                print(f"Download attempt #{attempt}")
                file_path = download_video(url, output_dir, quality, arg_dict["SESSDATA"], title=video_info,timeout=estimated_time)
                video['downloaded'] = 'True'
                video['file_path'] = str(file_path)
                save_to_csv(video_urls, csv_path)
                success = True
            except subprocess.TimeoutExpired:
                print(f"Timeout for {url}, will retry...")
                if progress_callback:
                    progress_callback(f"Timeout for {url}, retrying...\n")
            except subprocess.CalledProcessError as e:
                print(f"Error downloading {url}: {e}, will retry...")
                if progress_callback:
                    progress_callback(f"Error downloading {url}: {e}, retrying...\n")
            except Exception as e:
                print(f"Unexpected error downloading {url}: {e}, will retry...")
                if progress_callback:
                    progress_callback(f"Unexpected error downloading {url}: {e}, retrying...\n")

        if not success:
            video['downloaded'] = 'False'
            save_to_csv(video_urls, csv_path)
            if progress_callback:
                progress_callback(f"Failed to download {url} after {max_attempts} attempts.\n")
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