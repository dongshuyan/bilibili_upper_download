import gradio as gr
import asyncio
import subprocess
import os
import ffmpeg
from bilibili_upper_download import read_toml_config, get_user_name, get_user_video_urls, get_video_info, download_video
import time
# 语言字典（未更改）
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
        "total_videos_label": "Total Videos",
        "progress_label": "Progress (%)",
        "current_video_label": "Current Video",
        "duration_label": "Duration",
        "log_label": "Download Progress",
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
        "total_videos_label": "总视频数",
        "progress_label": "进度 (%)",
        "current_video_label": "当前视频",
        "duration_label": "时长",
        "log_label": "下载进度",
        "toggle_button": "切换到英文",
        "downloaded_videos_label": "已下载视频",
        "video_player_label": "视频播放器"
    }
}

def generate_thumbnail(video_path, output_dir):
    """生成或获取视频的缩略图"""
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    thumbnail_path = os.path.join(output_dir, f"{base_name}-poster.jpg")
    
    if os.path.exists(thumbnail_path):
        print(f"发现现有缩略图: {thumbnail_path}")
        return thumbnail_path
    
    # 如果没有现有的缩略图，抽取第一帧并保存
    try:
        print(f"正在为 {video_path} 生成缩略图...")
        stream = ffmpeg.input(video_path, ss=0)  # 提取第0秒（第一帧）
        stream = ffmpeg.output(stream, thumbnail_path, vframes=1, format='image2', q_v=2)
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
        if os.path.exists(thumbnail_path):
            print(f"成功生成并保存缩略图: {thumbnail_path}")
            return thumbnail_path
        else:
            print(f"缩略图生成失败，未找到文件: {thumbnail_path}")
            return video_path  # 生成失败时回退到视频路径
    except ffmpeg.Error as e:
        print(f"生成缩略图失败 {video_path}: {e.stderr.decode() if e.stderr else str(e)}")
        return video_path
    except Exception as e:
        print(f"未知错误生成缩略图 {video_path}: {str(e)}")
        return video_path

async def run_download(uid, output_dir, video_quality, sessdata, bili_jct, buvid3):
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
            if key in toml_args["basic"] and toml_args["basic"][key] != "" and toml_args["basic"][key] is not None:
                arg_dict[key] = toml_args["basic"][key]
    except Exception as e:
        yield {"log": f"加载 TOML 配置失败: {e}\n", "up_name": "", "total_videos": "", "current_video": "", "duration": "", "progress": 0, "downloaded_videos": []}
        return

    up_name = await get_user_name(int(uid))
    video_urls = await get_user_video_urls(int(uid))
    total_videos = len(video_urls)

    output_dir = os.path.expanduser(os.path.join(arg_dict["output_dir"], up_name))
    os.makedirs(output_dir, exist_ok=True)
    downloaded_videos = []

    yield {
        "log": f"获取 UID {uid} 的视频列表 (UP: {up_name})\n找到 {total_videos} 个视频待下载\n",
        "up_name": up_name,
        "total_videos": str(total_videos),
        "current_video": "",
        "duration": "",
        "progress": 0,
        "downloaded_videos": downloaded_videos
    }

    if not video_urls:
        yield {
            "log": "该用户没有找到视频。\n",
            "up_name": up_name,
            "total_videos": "0",
            "current_video": "",
            "duration": "",
            "progress": 0,
            "downloaded_videos": downloaded_videos
        }
        return

    log_file = os.path.join(os.path.dirname(__file__), "download_errors.log")
    for i, url in enumerate(video_urls, 1):
        print(f"正在下载视频 {i}/{len(video_urls)}")
        bvid = url.split("/")[-1]
        video_info = await get_video_info(bvid, arg_dict["SESSDATA"], arg_dict["BILI_JCT"], arg_dict["BUVID3"])
        current_video = video_info["title"]
        duration = str(video_info["duration"]) + "s"
        progress = round((i / total_videos) * 100, 2)
        
        yield {
            "log": f"开始下载 {i}/{total_videos}: {current_video}\n",
            "up_name": up_name,
            "total_videos": str(total_videos),
            "current_video": current_video,
            "duration": duration,
            "progress": progress,
            "downloaded_videos": downloaded_videos
        }

        estimated_time = 5 + video_info["duration"] * 2
        max_attempts = 5
        success = False
        attempt = 0

        while attempt < max_attempts and not success:
            attempt += 1
            try:
                yield {
                    "log": f"尝试 {attempt}/{max_attempts} 下载视频 {i}/{total_videos}: {current_video}\n",
                    "up_name": up_name,
                    "total_videos": str(total_videos),
                    "current_video": current_video,
                    "duration": duration,
                    "progress": progress,
                    "downloaded_videos": downloaded_videos
                }
                download_video(url, output_dir, arg_dict["video_quality"], arg_dict["SESSDATA"], title=current_video, timeout=estimated_time)
                success = True
                video_path = os.path.abspath(os.path.join(output_dir, f"{current_video}.mp4"))
                downloaded_videos.append(video_path)
                time.sleep(1)  # 等待文件写入
                thumbnail_path = generate_thumbnail(video_path, output_dir)
                progress = round((i / total_videos) * 100, 2)
                yield {
                    "log": f"成功下载 {i}/{total_videos}: {current_video}\n视频保存至: {video_path}\n缩略图: {thumbnail_path}\n",
                    "up_name": up_name,
                    "total_videos": str(total_videos),
                    "current_video": current_video,
                    "duration": duration,
                    "progress": progress,
                    "downloaded_videos": downloaded_videos
                }
            except subprocess.TimeoutExpired:
                yield {
                    "log": f"尝试 {attempt}/{max_attempts} 下载 {url} 超时，正在重试...\n",
                    "up_name": up_name,
                    "total_videos": str(total_videos),
                    "current_video": current_video,
                    "duration": duration,
                    "progress": progress,
                    "downloaded_videos": downloaded_videos
                }
            except subprocess.CalledProcessError as e:
                yield {
                    "log": f"尝试 {attempt}/{max_attempts} 下载 {url} 出错: {e}，正在重试...\n",
                    "up_name": up_name,
                    "total_videos": str(total_videos),
                    "current_video": current_video,
                    "duration": duration,
                    "progress": progress,
                    "downloaded_videos": downloaded_videos
                }
            except Exception as e:
                yield {
                    "log": f"尝试 {attempt}/{max_attempts} 下载 {url} 遇到未知错误: {e}，正在重试...\n",
                    "up_name": up_name,
                    "total_videos": str(total_videos),
                    "current_video": current_video,
                    "duration": duration,
                    "progress": progress,
                    "downloaded_videos": downloaded_videos
                }

        if not success:
            error_msg = f"下载 {url} 在 {max_attempts} 次尝试后失败。\n"
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(error_msg)
            yield {
                "log": error_msg,
                "up_name": up_name,
                "total_videos": str(total_videos),
                "current_video": current_video,
                "duration": duration,
                "progress": progress,
                "downloaded_videos": downloaded_videos
            }

    yield {
        "log": "下载全部完成！\n",
        "up_name": up_name,
        "total_videos": str(total_videos),
        "current_video": "",
        "duration": "",
        "progress": 100,
        "downloaded_videos": downloaded_videos
    }

def download_wrapper(uid, output_dir, video_quality, sessdata, bili_jct, buvid3):
    async def run_generator():
        async for result in run_download(uid, output_dir, video_quality, sessdata, bili_jct, buvid3):
            gallery_videos = []
            for video_path in result["downloaded_videos"][-50:]:
                base_name = os.path.splitext(os.path.basename(video_path))[0]
                thumbnail_path = os.path.join(os.path.dirname(video_path), f"{base_name}-poster.jpg")
                gallery_videos.append(thumbnail_path if os.path.exists(thumbnail_path) else video_path)
            yield (
                result["log"],
                result["up_name"],
                result["total_videos"],
                result["current_video"],
                result["duration"],
                result["progress"],
                gallery_videos,
                result["downloaded_videos"]
            )
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    gen = run_generator()
    
    try:
        while True:
            result = loop.run_until_complete(gen.__anext__())
            yield result
    except StopAsyncIteration:
        pass
    finally:
        loop.close()

async def load_video_with_timeout(video_path, timeout=5):
    """异步加载视频，带超时控制"""
    try:
        await asyncio.wait_for(asyncio.to_thread(lambda: os.path.exists(video_path)), timeout=timeout)
        return video_path if os.path.exists(video_path) else None
    except asyncio.TimeoutError:
        print(f"加载视频 {video_path} 超时，超过 {timeout} 秒")
        return None
    except Exception as e:
        print(f"加载视频 {video_path} 出错: {e}")
        return None

def play_video_from_gallery(evt: gr.SelectData, downloaded_videos):
    """从画廊中播放选中的视频"""
    if evt.index is None or not downloaded_videos:
        return gr.update(value=None)
    
    selected_video_path = downloaded_videos[-50:][evt.index]
    if os.path.exists(selected_video_path):
        print(f"尝试加载视频: {selected_video_path}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(load_video_with_timeout(selected_video_path, timeout=5))
        loop.close()
        return gr.update(value=result)
    print(f"未找到视频: {selected_video_path}")
    return gr.update(value=None)

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
            gr.update(label=texts['total_videos_label']),
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

    with gr.Blocks(title="Bilibili视频下载器", theme=gr.themes.Soft()) as demo:
        lang_state = gr.State(value="zh")
        downloaded_videos_state = gr.State(value=[])
        
        toggle_btn = gr.Button(value=TEXTS["zh"]["toggle_button"])
        title_md = gr.Markdown(f"# {TEXTS['zh']['title']}")
        desc_md = gr.Markdown(TEXTS["zh"]["description"])

        with gr.Row():
            with gr.Column(scale=1):
                uid_input = gr.Textbox(
                    label=TEXTS["zh"]["uid_label"],
                    placeholder=TEXTS["zh"]["uid_placeholder"],
                    lines=1
                )
                output_dir_input = gr.Textbox(
                    label=TEXTS["zh"]["output_dir_label"],
                    placeholder=TEXTS["zh"]["output_dir_placeholder"],
                    lines=1
                )
                quality_dropdown = gr.Dropdown(
                    label=TEXTS["zh"]["quality_label"],
                    choices=["127 (8K)", "126 (4K HDR)", "125 (4K)", "120 (1080p HDR)", "116 (1080p High)", 
                            "112 (1080p)", "100 (720p High)", "80 (720p)", "74 (480p High)", "64 (480p)", 
                            "32 (360p High)", "16 (360p)"],
                    value="127 (8K)"
                )
                
                credentials_accordion = gr.Accordion(TEXTS["zh"]["credentials_label"], open=False)
                with credentials_accordion:
                    sessdata_input = gr.Textbox(
                        label=TEXTS["zh"]["sessdata_label"],
                        placeholder=TEXTS["zh"]["sessdata_placeholder"],
                        lines=1,
                        type="password"
                    )
                    bili_jct_input = gr.Textbox(
                        label=TEXTS["zh"]["bili_jct_label"],
                        placeholder=TEXTS["zh"]["bili_jct_placeholder"],
                        lines=1,
                        type="password"
                    )
                    buvid3_input = gr.Textbox(
                        label=TEXTS["zh"]["buvid3_label"],
                        placeholder=TEXTS["zh"]["buvid3_placeholder"],
                        lines=1,
                        type="password"
                    )

                download_btn = gr.Button(TEXTS["zh"]["start_button"], variant="primary")

            with gr.Column(scale=2):
                with gr.Row():
                    with gr.Column(scale=1):
                        with gr.Row():
                            up_name_display = gr.Textbox(
                                label=TEXTS["zh"]["up_name_label"],
                                value="",
                                interactive=False,
                                elem_classes="short-textbox"
                            )
                            total_videos_display = gr.Textbox(
                                label=TEXTS["zh"]["total_videos_label"],
                                value="",
                                interactive=False,
                                elem_classes="short-textbox"
                            )
                            progress_bar = gr.Slider(
                                label=TEXTS["zh"]["progress_label"],
                                minimum=0,
                                maximum=100,
                                value=0,
                                interactive=False,
                                elem_classes="progress-bar"
                            )
                        with gr.Row():
                            current_video_display = gr.Textbox(
                                label=TEXTS["zh"]["current_video_label"],
                                value="",
                                interactive=False
                            )
                            duration_display = gr.Textbox(
                                label=TEXTS["zh"]["duration_label"],
                                value="",
                                interactive=False,
                                elem_classes="short-textbox"
                            )
                        output_log = gr.Textbox(
                            label=TEXTS["zh"]["log_label"],
                            lines=10,
                            interactive=False
                        )
                    with gr.Column(scale=1):
                        downloaded_videos_gallery = gr.Gallery(
                            label=TEXTS["zh"]["downloaded_videos_label"],
                            value=[],
                            height="400px",  # 固定高度，支持垂直滚动
                            preview=True,
                            object_fit="cover"
                        )
                        video_player = gr.Video(
                            label=TEXTS["zh"]["video_player_label"],
                            interactive=False
                        )

        demo.css = """
            .short-textbox { max-width: 200px; }
            .progress-bar { flex-grow: 1; margin-left: 10px; }
            video { max-height: 300px; width: 100%; }
            .gr-gallery { 
                display: grid; 
                grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));  # 网格布局，自动换行
                gap: 10px; 
                max-height: 400px;  # 与 Gallery 高度一致
                overflow-y: auto;  # 垂直滚动
                overflow-x: hidden;  # 禁止水平滚动
                padding: 10px; 
            }
            .gr-gallery img { 
                width: 100%; 
                height: 100px;  # 固定缩略图高度
                object-fit: cover; 
                cursor: pointer; 
            }
        """

        toggle_btn.click(
            fn=toggle_language,
            inputs=[lang_state],
            outputs=[
                title_md, desc_md, uid_input, output_dir_input, quality_dropdown,
                sessdata_input, bili_jct_input, buvid3_input,
                download_btn, up_name_display, total_videos_display, progress_bar,
                current_video_display, duration_display, output_log, toggle_btn,
                credentials_accordion, downloaded_videos_gallery, video_player, lang_state
            ]
        )

        download_btn.click(
            fn=download_wrapper,
            inputs=[uid_input, output_dir_input, quality_dropdown, sessdata_input, bili_jct_input, buvid3_input],
            outputs=[
                output_log, up_name_display, total_videos_display, current_video_display,
                duration_display, progress_bar, downloaded_videos_gallery, downloaded_videos_state
            ]
        )

        downloaded_videos_gallery.select(
            fn=play_video_from_gallery,
            inputs=[downloaded_videos_state],
            outputs=[video_player]
        )

    return demo

if __name__ == "__main__":
    webui = create_webui()
    webui.launch()