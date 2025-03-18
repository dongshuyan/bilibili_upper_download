# Bilibili 视频下载器

一个使用 `yutto` 工具和 `bilibili-api` 库的 Python 脚本，用于下载指定 Bilibili 用户的所有视频。

## 功能
- 根据用户 UID 获取并下载其所有视频。
- 支持自定义视频质量选择（例如 8K、4K、1080p 等）。
- 通过 TOML 文件配置凭据和设置。
- 下载失败时自动重试，并支持超时处理。
- 将下载失败记录到日志文件以便排查问题。

## 前提条件
- Python 3.7 或更高版本
- 已安装的依赖：
  - `bilibili-api-python` (`pip install bilibili-api-python`)
  - `yutto` (`pip install yutto`)
  - `toml` (`pip install toml`)
- 一个有效的 Bilibili 账户，并提供 `SESSDATA`、`BILI_JCT` 和 `BUVID3` 凭据（见配置部分）。

## 安装
1. 克隆或下载此仓库：

        git clone https://github.com/dongshuyan/bilibili_upper_download.git

        cd bilibili-video-downloader

2. 安装所需的 Python 包：

        pip install -r requirements.txt

3. 如果尚未安装 `yutto`，请安装它

        参考 https://github.com/yutto-dev/yutto?tab=readme-ov-file

4. 准备一个 `config.toml` 文件（见配置部分）。

## 使用方法
使用以下命令运行脚本：

python bilibili_upper_download.py -u <UID> [-o <OUTPUT_DIR>] [-q <QUALITY>]


### 参数
- `-u, --uid`：（必填）Bilibili 用户 UID（例如 `12345678`）。
- `-o, --output_dir`：（可选）保存下载视频的目录（默认：`~/Downloads`）。
- `-q, --video_quality`：（可选）视频质量代码（默认：`127`，即 8K）。可选值：
  - `127`：8K
  - `126`：4K HDR
  - `125`：4K
  - `120`：1080p HDR
  - `116`：1080p 高码率
  - `112`：1080p+
  - `100`：原画
  - `80`：720p
  - `74`：720p 高码率
  - `64`：480p
  - `32`：360p
  - `16`：240p

### 示例

        将 UID 为 `12345678` 的所有视频以 1080p 质量下载到 `/path/to/videos`：

        python bilibili_upper_download.py -u 12345678 -o /path/to/videos -q 116


## 配置
在脚本目录中创建 `config.toml` 文件，或指定自定义路径。文件中需包含 Bilibili 凭据和默认设置。

### 示例 `config.toml`
```toml
[basic]
uid = 0                  # 默认 UID（会被命令行参数覆盖）
output_dir = "~/Downloads"  # 默认输出目录
video_quality = "127"    # 默认视频质量（8K）
SESSDATA = "your_sessdata_here"  # Bilibili SESSDATA cookie
BILI_JCT = "your_bili_jct_here"  # Bilibili BILI_JCT cookie
BUVID3 = "your_buvid3_here"      # Bilibili BUVID3 cookie
```

### 如何获取上述 Bilibili 参数值
1. 在浏览器中登录 Bilibili。
2. 打开开发者工具（F12）> 网络（Network）选项卡。
3. 刷新页面，筛选请求（例如 api.bilibili.com）。
4. 在 Cookie 头中找到 SESSDATA、BILI_JCT 和 BUVID3。

### 错误处理
下载失败时，最多重试 5 次，重试超时基于视频时长动态调整。

持续失败的下载记录在脚本目录下的 download_errors.log 文件中。