import gradio as gr
import asyncio
import subprocess
import os
import pandas as pd
from bilibili_upper_download import read_toml_config, get_user_name, get_user_video_urls, get_video_info, download_video, save_to_csv, extract_and_convert_time, get_file_names
from pathlib import Path
import platform
import time
import json
import tempfile
import re

# Define the config file path
CONFIG_FILE = Path(__file__).parent / "config.json"

def load_config():
    """Load the previous configuration from a JSON file."""
    default_config = {
        "uid": "",
        "output_dir": "~/Downloads",
        "video_quality": "127 (8K)"
    }
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                for key in default_config:
                    if key not in config:
                        config[key] = default_config[key]
                return config
        except Exception as e:
            print(f"Error loading config: {e}")
            return default_config
    return default_config

def save_config(uid, output_dir, video_quality):
    print(f"Start saving current configuration to the JSON file: {CONFIG_FILE}.")
    config = {
        "uid": uid,
        "output_dir": output_dir,
        "video_quality": video_quality
    }
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        print(f"Save JSON file Successfully")
    except Exception as e:
        print(f"Error saving config: {e}")

TEXTS = {
    "en": {
        "title": "Bilibili Video Downloader",
        "description": "Download all videos from a Bilibili user by providing their UID and credentials.",
        "uid_label": "Bilibili UID",
        "uid_placeholder": "Enter the user's UID",
        "output_dir_label": "Output Directory",
        "output_dir_placeholder": "~/Downloads",
        "quality_label": "Video Quality",
        "credentials_label": "Bilibili Credentials (Optional if in config.toml)",
        "sessdata_label": "SESSDATA",
        "sessdata_placeholder": "Enter SESSDATA",
        "bili_jct_label": "BILI_JCT",
        "bili_jct_placeholder": "Enter BILI_JCT",
        "buvid3_label": "BUVID3",
        "buvid3_placeholder": "Enter BUVID3",
        "start_button": "Start Download",
        "up_name_label": "UP Name",
        "download_progress_label": "Download Progress (Current/Total)",
        "progress_label": "Progress (%)",
        "current_video_label": "Current Video",
        "duration_label": "Duration",
        "log_label": "Download Log",
        "toggle_button": "切换到中文",
        "downloaded_videos_label": "Downloaded Videos",
        "video_player_label": "Video Player",
        "dialog_message": "Video file size is {size:.2f}MB, exceeding 1GB. Please choose playback method:",
        "web_play_button": "Play in web",
        "local_play_button": "Play with local player (recommended)",
        "download_time_label": "Download Time",
        "download_speed_label": "Download Speed",
        "download_size_label": "Download size",
        "file_size_label": "File size",
        "abort_button": "Abort Current Attempt"
    },
    "zh": {
        "title": "Bilibili视频下载器",
        "description": "通过提供Bilibili用户的UID和凭证下载其所有视频。",
        "uid_label": "Bilibili UID",
        "uid_placeholder": "输入用户UID",
        "output_dir_label": "输出目录",
        "output_dir_placeholder": "~/Downloads",
        "quality_label": "视频质量",
        "credentials_label": "Bilibili凭证（如果在config.toml中可留空）",
        "sessdata_label": "SESSDATA(下载高清视频必须)",
        "sessdata_placeholder": "输入SESSDATA",
        "bili_jct_label": "BILI_JCT(目前非必须)",
        "bili_jct_placeholder": "输入BILI_JCT",
        "buvid3_label": "BUVID3(目前非必须)",
        "buvid3_placeholder": "输入BUVID3",
        "start_button": "开始下载",
        "up_name_label": "UP主名称",
        "download_progress_label": "下载进度 (当前/总数)",
        "progress_label": "进度 (%)",
        "current_video_label": "当前视频",
        "duration_label": "当前视频时长",
        "log_label": "下载日志",
        "toggle_button": "Switch to English",
        "downloaded_videos_label": "已下载视频",
        "video_player_label": "视频播放器",
        "dialog_message": "视频文件大小为 {size:.2f}MB，超过1GB，请选择播放方式：",
        "web_play_button": "在网页中播放",
        "local_play_button": "本地播放器播放 (推荐)",
        "download_time_label": "已下载时间",
        "download_speed_label": "下载速度",
        "download_size_label": "已下载大小",
        "file_size_label": "文件大小",
        "abort_button": "中止当前尝试"
    }
}

download_df = pd.DataFrame(columns=["Index", "Video Name", "Path", "Duration"])
abort_current = False

def format_time(seconds):
    """将秒数转换为 hh:mm:ss 格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def parse_download_speed(line):
    # print()
    # print('*'*20)
    # print(f"Line: {line}")
    if 'INFO' in line.upper():
        print(line)
    """解析下载速度，基于第二个 '/' 前面的数字和单位"""
    parts = line.split('/')
    file_size = 0
    download_size = 0
    speed_num = 0
    if len(parts) >= 3:  # 确保有至少两个 '/'（如 "18.82 GiB/ 24.19 GiB 766.48 KiB/s"）
        download_size_part = parts[0].strip().split()  # 取第一个 '/' 前面的部分，例如 "18.82 GiB"
        if len(re.findall(r'\d+\.?\d*',parts[0])) > 0:
            download_size=re.findall(r'\d+\.?\d*', parts[0])[-1]
            download_size = str(download_size) +' '+ download_size_part[-1] 
        else:
            download_size = '0 KiB'   
        
        file_size_part = parts[1].strip().split()  # 取第二个 '/' 前面的部分，例如 "24.19 GiB" 
        if len(re.findall(r'\d+\.?\d*',file_size_part[0])) > 0:
            file_size=re.findall(r'\d+\.?\d*', file_size_part[0])[-1]
            file_size = str(file_size) +' '+ file_size_part[1] 
        else:
            file_size = '0 KiB'   
        
        speed_part = parts[-2].strip()  # 取第二个 '/' 后面的部分，例如 "766.48 KiB/s"
        speed_components = speed_part.split()  # 按空格分割，例如 ["766.48", "KiB/s"]
        if len(speed_components) >= 2:
            # print(f"Speed components: {speed_components}")
            # print(f"speed_components[-2]: {speed_components[-2]}")
            if len(re.findall(r'\d+\.?\d*', speed_components[-2])) > 0:
                speed_num=re.findall(r'\d+\.?\d*', speed_components[-2])[-1]
            else:
                speed_num = 0
            # print(f"Speed: {speed_num} {speed_components[-1]}/s")
            # print('#'*20)
            # print()
            return download_size, file_size ,f"{speed_num} {speed_components[-1]}/s" 
    return "0 KiB","0 KiB","0 KiB/s" 


async def run_download(uid, output_dir, video_quality, sessdata, bili_jct, buvid3):
    global download_df, abort_current
    quality_value = video_quality.split(" ")[0]
    
    arg_dict = {
        "uid": int(uid),
        "output_dir": str(output_dir if output_dir else "~/Downloads"),
        "video_quality": str(quality_value),
        "SESSDATA": sessdata,
        "BILI_JCT": bili_jct,
        "BUVID3": buvid3,
    }

    try:
        toml_args = read_toml_config()
        for key in arg_dict:
            if key in toml_args["basic"] and toml_args["basic"][key] and (arg_dict[key] is None or arg_dict[key] == ""):
                arg_dict[key] = toml_args["basic"][key]
    except Exception as e:
        yield {"log": f"Error loading TOML config: {e}\n", "up_name": "", "download_progress": "", "current_video": "", "duration": "", "download_time": "00:00:00", "download_speed": "0 KiB/s","download_size": "0 KiB", "file_size": "0 KiB", "progress": 0}
        return

    up_name = await get_user_name(int(uid))
    yield {
        "log": f"Fetching video list for UID: {uid} (UP: {up_name})\n",
        "up_name": up_name,
        "download_progress": "",
        "current_video": "",
        "duration": "",
        "download_time": "00:00:00",
        "download_speed": "0 KiB/s",
        "download_size": "0 KiB",
        "file_size": "0 KiB",
        "progress": 0
    }

    output_dir = os.path.expanduser(os.path.join(arg_dict["output_dir"], up_name))
    os.makedirs(output_dir, exist_ok=True)
    csv_path = Path(output_dir) / "video_urls.csv"
    
    video_urls = await get_user_video_urls(int(uid), output_dir)
    total_videos = len(video_urls)

    yield {
        "log": f"Fetching video list for UID: {uid} (UP: {up_name})\nFound {total_videos} videos to download\n",
        "up_name": up_name,
        "download_progress": f"0/{total_videos}",
        "current_video": "",
        "duration": "",
        "download_time": "00:00:00",
        "download_speed": "0 KiB/s",
        "download_size": "0 KiB",
        "file_size": "0 KiB",
        "progress": 0
    }

    if not video_urls:
        yield {
            "log": "No videos found for this user.\n",
            "up_name": up_name,
            "download_progress": "",
            "current_video": "",
            "duration": "",
            "download_time": "00:00:00",
            "download_speed": "0 KiB/s",
            "download_size": "0 KiB",
            "file_size": "0 KiB",
            "progress": 0
        }
        return

    log_file = os.path.join(os.path.dirname(__file__), "download_errors.log")
    for i, video in enumerate(video_urls, 1):
        url = video['url']
        if video['downloaded'] == 'True':
            print(f"Skipping already downloaded video {i}/{total_videos}: {video['title']}")
            continue

        print(f"Downloading video {i}/{len(video_urls)}")
        bvid = url.split("/")[-1]
        video_info = await get_video_info(bvid, arg_dict["SESSDATA"], arg_dict["BILI_JCT"], arg_dict["BUVID3"])
        
        if len(video_info['pages']) < 1:
            print(f"Skipping disappeared video {i}/{total_videos}: {video['url']}")
            continue

        video['title'] = video_info['title']
        video['duration'] = extract_and_convert_time(str(video_info['duration']))
        video['info'] = str(video_info)
        save_to_csv(video_urls, csv_path)
        print("updated video info to csv")

        current_video = video_info["title"]
        duration = f"{video['duration']}"
        progress = round((i / total_videos) * 100, 2)

        yield {
            "log": f"Starting download {i}/{total_videos}: {current_video}\n",
            "up_name": up_name,
            "download_progress": f"{i}/{total_videos}",
            "current_video": current_video,
            "duration": duration,
            "download_time": "00:00:00",
            "download_speed": "0 KiB/s",
            "download_size": "0 KiB",
            "file_size": "0 KiB",
            "progress": progress
        }

        max_attempts = 5
        success = False
        is_completed = False
        attempt = 0

        while attempt < max_attempts and not success:
            attempt += 1
            abort_current = False
            start_time = time.time()
            process = None
            
            # 创建临时文件用于捕获输出
            with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
                temp_file_path = temp_file.name

                try:
                    if len(video_info['pages']) > 1:
                        command = [
                            "yutto",
                            "--sessdata", str(arg_dict["SESSDATA"]),
                            "-d", str(output_dir),
                            "-q", str(arg_dict["video_quality"]),
                            "-b",
                            "-p", "1~-1",
                            "--download-interval", "2",
                            "--save-cover",
                            url
                        ]
                    else:
                        command = [
                            "yutto",
                            "--sessdata", str(arg_dict["SESSDATA"]),
                            "-d", str(output_dir),
                            "-q", str(arg_dict["video_quality"]),
                            "--download-interval", "2",
                            "--save-cover",
                            url
                        ]
                    
                    # 使用 tee 将输出同时显示在终端并写入临时文件
                    tee_command = command + ["|", "tee", temp_file_path] if platform.system() != "Windows" else command
                    process = subprocess.Popen(
                        " ".join(tee_command) if platform.system() != "Windows" else command,
                        shell=True  # 需要 shell=True 来支持 tee
                    )
                    
                    download_speed = "0 KiB/s"
                    download_size= "0 KiB"
                    file_size= "0 KiB"
                    
                    # 读取临时文件并解析速度
                    last_pos = 0
                    while process.poll() is None:
                        if abort_current:
                            process.terminate()
                            raise Exception("Download aborted by user")
                        elapsed_time = time.time() - start_time
                        
                        with open(temp_file_path, 'r', encoding='utf-8', errors='replace') as f:
                            f.seek(last_pos)
                            new_lines = f.readlines()
                            last_pos = f.tell()
                            
                            for line in new_lines:
                                if '/' in line:
                                    download_size, file_size ,download_speed = parse_download_speed(line)
                                    yield {
                                        "log": f"Progress update: {line.strip()}\n",
                                        "up_name": up_name,
                                        "download_progress": f"{i}/{total_videos}",
                                        "current_video": current_video,
                                        "duration": duration,
                                        "download_time": format_time(elapsed_time),

                                        "download_speed": download_speed,
                                        "download_size": download_size,
                                        "file_size": file_size,
                                        "progress": progress
                                    }
                        
                        yield {
                            "log": f"Attempt {attempt}/{max_attempts} downloading {current_video}\n",
                            "up_name": up_name,
                            "download_progress": f"{i}/{total_videos}",
                            "current_video": current_video,
                            "duration": duration,
                            "download_time": format_time(elapsed_time),
                            "download_speed": download_speed,
                            "download_size": download_size,
                            "file_size": file_size,
                            "progress": progress
                        }
                        await asyncio.sleep(0.1)
                    
                    # 进程结束后，检查是否包含“合并完成”
                    with open(temp_file_path, 'r', encoding='utf-8', errors='replace') as f:
                        full_output = f.read()
                        if "合并完成" in full_output:
                            is_completed = True

                    if is_completed:
                    # if process.returncode == 0:
                        video_path = get_file_names(output_dir, video_info)
                        success = True
                        
                        new_row = pd.DataFrame({
                            "Index": [i],
                            "Video Name": [current_video],
                            "Path": [video_path[0]],
                            "Duration": [duration]
                        })
                        download_df = pd.concat([new_row, download_df], ignore_index=True)
                        yield {
                            "log": f"Successfully downloaded {i}/{total_videos}: {current_video}\nVideo saved at: {video_path}\n",
                            "up_name": up_name,
                            "download_progress": f"{i}/{total_videos}",
                            "current_video": current_video,
                            "duration": duration,
                            "download_time": format_time(time.time() - start_time),
                            "download_speed": download_speed,
                            "download_size": download_size,
                            "file_size": file_size,
                            "progress": progress
                        }

                        video['downloaded'] = 'True'
                        video['file_path'] = str(video_path)
                        save_to_csv(video_urls, csv_path)
                        print("updated download success status to csv")
                    else:
                        print("Yutto is not completed")

                except Exception as e:
                    if process:
                        process.terminate()
                    elapsed_time = time.time() - start_time
                    yield {
                        "log": f"Attempt {attempt}/{max_attempts} failed for {current_video}: {e}\n",
                        "up_name": up_name,
                        "download_progress": f"{i}/{total_videos}",
                        "current_video": current_video,
                        "duration": duration,
                        "download_time": format_time(elapsed_time),
                        "download_speed": download_speed,
                        "download_size": download_size,
                        "file_size": file_size,
                        "progress": progress
                    }
                    print(f"Attempt {attempt}/{max_attempts} failed for {current_video}: {e}\n")
                
                finally:
                    os.unlink(temp_file_path)  # 删除临时文件

        if not success:
            video['downloaded'] = 'False'
            save_to_csv(video_urls, csv_path)
            print("updated download failed status to csv")
            error_msg = f"Failed to download {url} after {max_attempts} attempts.\n"
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(error_msg)
            yield {
                "log": error_msg,
                "up_name": up_name,
                "download_progress": f"{i}/{total_videos}",
                "current_video": current_video,
                "duration": duration,
                "download_time": "00:00:00",
                "download_speed": "0 KiB/s",
                "download_size": "0 KiB",
                "file_size": "0 KiB",
                "progress": progress
            }

    yield {
        "log": "Download completed successfully!\n",
        "up_name": up_name,
        "download_progress": f"{total_videos}/{total_videos}",
        "current_video": "",
        "duration": "",
        "download_time": "00:00:00",
        "download_speed": "0 KiB/s",
        "download_size": "0 KiB",
        "file_size": "0 KiB",
        "progress": 100
    }

def play_video(evt: gr.SelectData, lang):
    global download_df
    if evt.index and len(evt.index) > 0:
        row_index = evt.index[0]
        if row_index < len(download_df):
            video_path = download_df.iloc[row_index]["Path"]
            print(f"Selected video: {video_path}")
            
            if os.path.exists(video_path):
                file_size = os.path.getsize(video_path)
                size_limit = 1 * 1024 * 1024 * 1024
                
                if file_size <= size_limit:
                    print(f"File size {file_size/(1024*1024)}MB <= 1G, playing in web")
                    return video_path, gr.update(visible=False), ""
                else:
                    print(f"File size {file_size/(1024*1024)}MB > 1G, showing dialog")
                    dialog_msg = f"## {TEXTS[lang]['dialog_message'].format(size=file_size/(1024*1024))}"
                    return None, gr.update(visible=True), dialog_msg
            else:
                print(f"Video file not found: {video_path}")
    print("No valid selection, hiding dialog")
    return None, gr.update(visible=False), ""

def handle_playback_choice(choice, video_path):
    if choice == TEXTS["zh"]["web_play_button"] or choice == TEXTS["en"]["web_play_button"]:
        print(f"Playing in web: {video_path}")
        return video_path, gr.update(visible=False)
    elif choice == TEXTS["zh"]["local_play_button"] or choice == TEXTS["en"]["local_play_button"]:
        print(f"Opening with local player: {video_path}")
        try:
            system = platform.system()
            if system == "Windows":
                os.startfile(video_path)
            elif system == "Darwin":
                subprocess.run(["open", video_path], check=True)
            else:
                subprocess.run(["xdg-open", video_path], check=True)
            print(f"Opened video file: {video_path}")
        except Exception as e:
            print(f"Error opening video file {video_path}: {e}")
    return None, gr.update(visible=False)

def download_wrapper(uid, output_dir, video_quality, sessdata, bili_jct, buvid3):
    global download_df, abort_current
    save_config(uid, output_dir, video_quality)
    
    async def run_generator():
        async for result in run_download(uid, output_dir, video_quality, sessdata, bili_jct, buvid3):
            yield (
                result["log"],
                gr.update(value=result["up_name"], visible=bool(result["up_name"])),
                gr.update(value=result["download_progress"], visible=bool(result["download_progress"])),
                result["current_video"],
                result["duration"],
                result["download_time"],
                result["download_speed"],
                result["download_size"],
                result["file_size"],
                gr.update(value=result["progress"], visible=True if result["progress"] > 0 else False),
                download_df[["Index", "Video Name", "Duration"]]
            )
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    gen = run_generator()
    try:
        while True:
            yield loop.run_until_complete(gen.__anext__())
    except StopAsyncIteration:
        pass
    finally:
        loop.close()

def abort_download():
    global abort_current
    abort_current = True
    return "Aborting current download attempt...\n"

def create_webui():
    config = load_config()

    def toggle_language(current_lang):
        new_lang = "en" if current_lang == "zh" else "zh"
        texts = TEXTS[new_lang]
        return [
            gr.update(value=f"# {texts['title']}"),
            gr.update(value=texts['description']),
            gr.update(label=texts['uid_label'], placeholder=texts['uid_placeholder']),
            gr.update(label=texts['output_dir_label'], placeholder=texts['output_dir_placeholder']),
            gr.update(label=texts['quality_label']),
            gr.update(label=texts['sessdata_label'], placeholder=texts['sessdata_placeholder']),
            gr.update(label=texts['bili_jct_label'], placeholder=texts['bili_jct_placeholder']),
            gr.update(label=texts['buvid3_label'], placeholder=texts['buvid3_placeholder']),
            gr.update(value=texts['start_button']),
            gr.update(label=texts['up_name_label']),
            gr.update(label=texts['download_progress_label']),
            gr.update(label=texts['progress_label']),
            gr.update(label=texts['current_video_label']),
            gr.update(label=texts['duration_label']),
            gr.update(label=texts['log_label']),
            gr.update(value=texts['toggle_button']),
            gr.update(label=texts['credentials_label']),
            gr.update(label=texts['downloaded_videos_label']),
            gr.update(label=texts['video_player_label']),
            gr.update(value=texts['start_button']),
            gr.update(value=texts['web_play_button']),
            gr.update(value=texts['local_play_button']),
            gr.update(label=texts['download_time_label']),
            gr.update(label=texts['download_speed_label']),
            gr.update(label=texts['download_size_label']),
            gr.update(label=texts['file_size_label']),
            gr.update(value=texts['abort_button']),
            new_lang
        ]

    with gr.Blocks(title="Bilibili Video Downloader", theme=gr.themes.Soft()) as demo:
        lang_state = gr.State(value="zh")
        selected_video_path = gr.State(value=None)

        toggle_btn = gr.Button(value=TEXTS["zh"]["toggle_button"])
        title_md = gr.Markdown(f"# {TEXTS['zh']['title']}")
        desc_md = gr.Markdown(TEXTS["zh"]["description"])

        with gr.Row():
            with gr.Column(scale=1):
                uid_input = gr.Textbox(
                    label=TEXTS["zh"]["uid_label"], 
                    placeholder=TEXTS["zh"]["uid_placeholder"],
                    value=config["uid"]
                )
                up_name_display = gr.Textbox(
                    label=TEXTS["zh"]["up_name_label"], 
                    interactive=False,
                    visible=False
                )
                output_dir_input = gr.Textbox(
                    label=TEXTS["zh"]["output_dir_label"], 
                    placeholder=TEXTS["zh"]["output_dir_placeholder"],
                    value=config["output_dir"]
                )
                quality_dropdown = gr.Dropdown(
                    label=TEXTS["zh"]["quality_label"],
                    choices=["127 (8K)", "126 (4K HDR)", "125 (4K)", "120 (1080p HDR)", "116 (1080p High)", 
                             "112 (1080p)", "100 (720p High)", "80 (720p)", "74 (480p High)", "64 (480p)", 
                             "32 (360p High)", "16 (360p)"],
                    value=config["video_quality"]
                )
                download_progress_display = gr.Textbox(
                    label=TEXTS["zh"]["download_progress_label"], 
                    interactive=False, 
                    visible=False
                )
                progress_bar = gr.Slider(
                    label=TEXTS["zh"]["progress_label"], 
                    minimum=0, 
                    maximum=100, 
                    interactive=False,
                    visible=False
                )
                credentials_accordion = gr.Accordion(TEXTS["zh"]["credentials_label"], open=False)
                with credentials_accordion:
                    sessdata_input = gr.Textbox(label=TEXTS["zh"]["sessdata_label"], placeholder=TEXTS["zh"]["sessdata_placeholder"], type="password")
                    bili_jct_input = gr.Textbox(label=TEXTS["zh"]["bili_jct_label"], placeholder=TEXTS["zh"]["bili_jct_placeholder"], type="password")
                    buvid3_input = gr.Textbox(label=TEXTS["zh"]["buvid3_label"], placeholder=TEXTS["zh"]["buvid3_placeholder"], type="password")
                download_btn = gr.Button(TEXTS["zh"]["start_button"], variant="primary")

            with gr.Column(scale=2):
                with gr.Row():
                    with gr.Column(scale=1):
                        current_video_display = gr.Textbox(label=TEXTS["zh"]["current_video_label"], interactive=False)
                        with gr.Row():
                            duration_display = gr.Textbox(label=TEXTS["zh"]["duration_label"], interactive=False)
                            download_time_display = gr.Textbox(label=TEXTS["zh"]["download_time_label"], interactive=False, value="00:00:00")
                            download_size_display = gr.Textbox(label=TEXTS["zh"]["download_size_label"], interactive=False, value="0 KiB")
                            file_size_display = gr.Textbox(label=TEXTS["zh"]["file_size_label"], interactive=False, value="0 KiB")
                            download_speed_display = gr.Textbox(label=TEXTS["zh"]["download_speed_label"], interactive=False, value="0 KiB/s")
                        abort_button = gr.Button(TEXTS["zh"]["abort_button"], variant="stop")
                        output_log = gr.Textbox(label=TEXTS["zh"]["log_label"], lines=10, interactive=False)
                    with gr.Column(scale=2):
                        downloaded_videos_df = gr.Dataframe(
                            label=TEXTS["zh"]["downloaded_videos_label"],
                            interactive=True,
                            height=200
                        )
                        with gr.Group(visible=False) as dialog_group:
                            dialog_text = gr.Markdown(value="", elem_classes="dialog-text")
                            with gr.Row():
                                web_play_btn = gr.Button(TEXTS["zh"]["web_play_button"], variant="secondary", elem_classes="dialog-btn")
                                local_play_btn = gr.Button(TEXTS["zh"]["local_play_button"], variant="primary", elem_classes="dialog-btn")
                        video_player = gr.Video(label=TEXTS["zh"]["video_player_label"], interactive=False)

        demo.css = """
            video { max-height: 300px; width: 100%; }
            .gr-dataframe { 
                width: 100% !important; 
                min-width: 600px; 
                max-width: 800px; 
            }
            .gr-dataframe table { 
                width: 100%; 
                table-layout: auto; 
            }
            .gr-dataframe th, .gr-dataframe td { 
                padding: 5px; 
                white-space: normal;
                word-wrap: break-word; 
                max-width: 0;
            }
            .gr-dataframe th:nth-child(1), .gr-dataframe td:nth-child(1) { width: 50px; }
            .gr-dataframe th:nth-child(2), .gr-dataframe td:nth-child(2) { width: 70%; }
            .gr-dataframe th:nth-child(3), .gr-dataframe td:nth-child(3) { width: 100px; }
            .dialog-text { 
                width: 100%; 
                margin-bottom: 10px; 
                padding: 10px;
            }
            .dialog-text h2 { 
                margin: 0;
                padding: 0;
            }
            .dialog-btn { 
                width: 200px; 
                margin: 0 10px; 
            }
            .dialog-btn.gr-button-primary { 
                font-weight: bold; 
            }
            .gr-textbox { 
                border: none !important;
                box-shadow: none !important;
            }
            .gr-slider { 
                border: none !important;
                box-shadow: none !important;
            }
        """

        toggle_btn.click(
            fn=toggle_language,
            inputs=[lang_state],
            outputs=[
                title_md, desc_md, uid_input, output_dir_input, quality_dropdown,
                sessdata_input, bili_jct_input, buvid3_input, download_btn,
                up_name_display, download_progress_display,
                progress_bar, current_video_display, duration_display, output_log,
                toggle_btn, credentials_accordion, downloaded_videos_df, video_player,
                download_btn, web_play_btn, local_play_btn,
                download_time_display, download_speed_display, download_size_display, file_size_display, abort_button,
                lang_state
            ]
        )

        download_btn.click(
            fn=download_wrapper,
            inputs=[uid_input, output_dir_input, quality_dropdown, sessdata_input, bili_jct_input, buvid3_input],
            outputs=[
                output_log, up_name_display, download_progress_display,
                current_video_display, duration_display, download_time_display,
                download_speed_display, download_size_display, file_size_display, progress_bar, downloaded_videos_df
            ]
        )

        abort_button.click(
            fn=abort_download,
            inputs=None,
            outputs=[output_log]
        )

        def update_selected_path(evt: gr.SelectData):
            global download_df
            if evt.index and len(evt.index) > 0:
                row_index = evt.index[0]
                if row_index < len(download_df):
                    return download_df.iloc[row_index]["Path"]
            return None

        downloaded_videos_df.select(
            fn=play_video,
            inputs=[lang_state],
            outputs=[video_player, dialog_group, dialog_text]
        )

        downloaded_videos_df.select(
            fn=update_selected_path,
            inputs=None,
            outputs=[selected_video_path]
        )

        web_play_btn.click(
            fn=handle_playback_choice,
            inputs=[gr.State(value=TEXTS["zh"]["web_play_button"]), selected_video_path],
            outputs=[video_player, dialog_group]
        )
        
        local_play_btn.click(
            fn=handle_playback_choice,
            inputs=[gr.State(value=TEXTS["zh"]["local_play_button"]), selected_video_path],
            outputs=[video_player, dialog_group]
        )

    return demo

if __name__ == "__main__":
    webui = create_webui()
    webui.launch()