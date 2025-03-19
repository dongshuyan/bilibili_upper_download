import gradio as gr
import asyncio
import subprocess
import os
import pandas as pd
from bilibili_upper_download import read_toml_config, get_user_name, get_user_video_urls, get_video_info, download_video, save_to_csv, extract_and_convert_time
from pathlib import Path


# Language dictionaries (保持不变)
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
        "toggle_button": "Switch to Chinese",
        "downloaded_videos_label": "Downloaded Videos",
        "video_player_label": "Video Player"
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
        "sessdata_label": "SESSDATA",
        "sessdata_placeholder": "输入SESSDATA",
        "bili_jct_label": "BILI_JCT",
        "bili_jct_placeholder": "输入BILI_JCT",
        "buvid3_label": "BUVID3",
        "buvid3_placeholder": "输入BUVID3",
        "start_button": "开始下载",
        "up_name_label": "UP主名称",
        "download_progress_label": "下载进度 (当前/总数)",
        "progress_label": "进度 (%)",
        "current_video_label": "当前视频",
        "duration_label": "时长",
        "log_label": "下载日志",
        "toggle_button": "切换到英文",
        "downloaded_videos_label": "已下载视频",
        "video_player_label": "视频播放器"
    }
}

# 初始化全局 DataFrame，添加序号和时长列
download_df = pd.DataFrame(columns=["Index", "Video Name", "Path", "Duration"])

async def run_download(uid, output_dir, video_quality, sessdata, bili_jct, buvid3):
    global download_df
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
        yield {"log": f"Error loading TOML config: {e}\n", "up_name": "", "download_progress": "0/0", "current_video": "", "duration": "", "progress": 0}
        return

    

    


    up_name = await get_user_name(int(uid))
    yield {
        "log": f"Fetching video list for UID: {uid} (UP: {up_name})\n",
        "up_name": up_name,
        "download_progress": f"0/?",
        "current_video": "",
        "duration": "",
        "progress": 0
    }

    output_dir = os.path.expanduser(os.path.join(arg_dict["output_dir"], up_name))
    os.makedirs(output_dir, exist_ok=True)
    csv_path = Path(output_dir) / "video_urls.csv"
    
    video_urls = await get_user_video_urls(int(uid),output_dir)
    total_videos = len(video_urls)

    

    yield {
        "log": f"Fetching video list for UID: {uid} (UP: {up_name})\nFound {total_videos} videos to download\n",
        "up_name": up_name,
        "download_progress": f"0/{total_videos}",
        "current_video": "",
        "duration": "",
        "progress": 0
    }

    if not video_urls:
        yield {
            "log": "No videos found for this user.\n",
            "up_name": up_name,
            "download_progress": "0/0",
            "current_video": "",
            "duration": "",
            "progress": 0
        }
        return

    log_file = os.path.join(os.path.dirname(__file__), "download_errors.log")
    for i, video in enumerate(video_urls, 1):
        # a=input("Press Enter to continue")
        url = video['url']
        if video['downloaded'] == 'True':
            print(f"Skipping already downloaded video {i}/{total_videos}: {video['title']}")
            continue

        print(f"Downloading video {i}/{len(video_urls)}")
        bvid = url.split("/")[-1]
        video_info = await get_video_info(bvid, arg_dict["SESSDATA"], arg_dict["BILI_JCT"], arg_dict["BUVID3"])
        
        # 更新视频信息
        video['title'] = video_info['title']
        # video['duration'] = str(video_info['duration'])
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
            "progress": progress
        }

        max_attempts = 5
        success = False
        attempt = 0

        while attempt < max_attempts and not success:
            attempt += 1
            try:
                video_path=download_video(url, output_dir, arg_dict["video_quality"], arg_dict["SESSDATA"], video_info=video_info, timeout=5 + video_info["duration"] * 2)
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
                    "progress": progress
                }

                video['downloaded'] = 'True'
                video['file_path'] = str(video_path)
                save_to_csv(video_urls, csv_path)
                print("updated download success status to csv")

            except Exception as e:
                yield {
                    "log": f"Attempt {attempt}/{max_attempts} failed for {current_video}: {e}\n",
                    "up_name": up_name,
                    "download_progress": f"{i}/{total_videos}",
                    "current_video": current_video,
                    "duration": duration,
                    "progress": progress
                }
                print(f"Attempt {attempt}/{max_attempts} failed for {current_video}: {e}\n")

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
                "progress": progress
            }

    yield {
        "log": "Download completed successfully!\n",
        "up_name": up_name,
        "download_progress": f"{total_videos}/{total_videos}",
        "current_video": "",
        "duration": "",
        "progress": 100
    }

def download_wrapper(uid, output_dir, video_quality, sessdata, bili_jct, buvid3):
    global download_df
    async def run_generator():
        async for result in run_download(uid, output_dir, video_quality, sessdata, bili_jct, buvid3):
            yield (
                result["log"],
                result["up_name"],
                result["download_progress"],
                result["current_video"],
                result["duration"],
                result["progress"],
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

def play_video(evt: gr.SelectData):
    global download_df
    if evt.index and len(evt.index) > 0:
        row_index = evt.index[0]
        if row_index < len(download_df):
            video_path = download_df.iloc[row_index]["Path"]
            print(f"Playing video: {video_path}")
            if os.path.exists(video_path):
                print(f"Playing exist video: {video_path}")
                return video_path
            else:
                print(f"Video file not found: {video_path}")
    return None

def create_webui():
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
            new_lang
        ]

    with gr.Blocks(title="Bilibili Video Downloader", theme=gr.themes.Soft()) as demo:
        lang_state = gr.State(value="zh")

        toggle_btn = gr.Button(value=TEXTS["zh"]["toggle_button"])
        title_md = gr.Markdown(f"# {TEXTS['zh']['title']}")
        desc_md = gr.Markdown(TEXTS["zh"]["description"])

        with gr.Row():
            with gr.Column(scale=1):
                uid_input = gr.Textbox(label=TEXTS["zh"]["uid_label"], placeholder=TEXTS["zh"]["uid_placeholder"])
                output_dir_input = gr.Textbox(label=TEXTS["zh"]["output_dir_label"], placeholder=TEXTS["zh"]["output_dir_placeholder"])
                quality_dropdown = gr.Dropdown(
                    label=TEXTS["zh"]["quality_label"],
                    choices=["127 (8K)", "126 (4K HDR)", "125 (4K)", "120 (1080p HDR)", "116 (1080p High)", 
                             "112 (1080p)", "100 (720p High)", "80 (720p)", "74 (480p High)", "64 (480p)", 
                             "32 (360p High)", "16 (360p)"],
                    value="127 (8K)"
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
                        with gr.Row():
                            up_name_display = gr.Textbox(label=TEXTS["zh"]["up_name_label"], interactive=False)
                            download_progress_display = gr.Textbox(label=TEXTS["zh"]["download_progress_label"], interactive=False, value="0/0")
                        progress_bar = gr.Slider(label=TEXTS["zh"]["progress_label"], minimum=0, maximum=100, interactive=False)
                        with gr.Row():
                            current_video_display = gr.Textbox(label=TEXTS["zh"]["current_video_label"], interactive=False)
                            duration_display = gr.Textbox(label=TEXTS["zh"]["duration_label"], interactive=False)
                        output_log = gr.Textbox(label=TEXTS["zh"]["log_label"], lines=10, interactive=False)
                    with gr.Column(scale=2):
                        downloaded_videos_df = gr.Dataframe(
                            label=TEXTS["zh"]["downloaded_videos_label"],
                            interactive=True,
                            height=200
                        )
                        video_player = gr.Video(label=TEXTS["zh"]["video_player_label"], interactive=False)

        # 增强 CSS 来控制 Dataframe 宽度
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
                white-space: normal;  /* 允许换行 */
                word-wrap: break-word; 
                max-width: 0;  /* 防止过宽 */
            }
            .gr-dataframe th:nth-child(1), .gr-dataframe td:nth-child(1) {  /* Index 列 */
                width: 50px;
            }
            .gr-dataframe th:nth-child(2), .gr-dataframe td:nth-child(2) {  /* Video Name 列 */
                width: 70%;
            }
            .gr-dataframe th:nth-child(3), .gr-dataframe td:nth-child(3) {  /* Duration 列 */
                width: 100px;
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
                lang_state
            ]
        )

        download_btn.click(
            fn=download_wrapper,
            inputs=[uid_input, output_dir_input, quality_dropdown, sessdata_input, bili_jct_input, buvid3_input],
            outputs=[
                output_log, up_name_display, download_progress_display,
                current_video_display, duration_display, progress_bar, downloaded_videos_df
            ]
        )

        downloaded_videos_df.select(
            fn=play_video,
            inputs=None,
            outputs=video_player
        )

    return demo

if __name__ == "__main__":
    webui = create_webui()
    webui.launch()