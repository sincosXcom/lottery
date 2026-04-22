import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import os
import tempfile
import cv2
from PIL import Image

st.set_page_config(page_title="快乐8视频生成器", layout="wide")
st.title("🎬 快乐8 视频生成器（独立版）")
st.markdown("生成单期动画或3期滑动窗口视频，支持下载HTML/MP4。")

# -----------------------------
# 数据加载（支持上传或内置演示数据）
# -----------------------------
# 数据加载（优先使用真实数据文件，否则使用演示数据）
@st.cache_data
def load_data():
    # 尝试读取本地数据文件（需要上传到仓库）
    file_path = "data/kl8.csv"
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        num_cols = [f"n{i}" for i in range(1, 21)]
        if all(col in df.columns for col in num_cols):
            df["号码列表"] = df[num_cols].apply(lambda row: sorted(row.tolist()), axis=1)
            if "issue" in df.columns:
                df.rename(columns={"issue": "期号"}, inplace=True)
            return df
    # 如果文件不存在，则使用演示数据
    np.random.seed(42)
    n_periods = 100
    period_numbers = []
    issues = list(range(2026001, 2026001 + n_periods))
    for i in range(n_periods):
        nums = np.random.choice(range(1, 81), size=20, replace=False)
        period_numbers.append(sorted(nums))
    df = pd.DataFrame({
        "期号": issues,
        "号码列表": period_numbers
    })
    return df

df = load_data()

data_source = st.sidebar.radio("数据来源", ["使用内置演示数据", "上传CSV文件"])
if data_source == "上传CSV文件":
    uploaded_file = st.sidebar.file_uploader("上传CSV文件", type=["csv"])
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        # 尝试自动识别号码列
        num_cols = [f"n{i}" for i in range(1, 21)]
        if all(col in df.columns for col in num_cols):
            df["号码列表"] = df[num_cols].apply(lambda row: sorted(row.tolist()), axis=1)
        elif "号码列表" in df.columns:
            # 如果已存在列表列，直接使用
            pass
        else:
            st.error("CSV格式错误，需要 n1~n20 列或预先生成的 '号码列表' 列")
            st.stop()
        if "期号" not in df.columns:
            df["期号"] = range(1, len(df)+1)
        st.success(f"已加载 {len(df)} 期数据")
    else:
        st.info("请上传CSV文件，或使用演示数据")
        st.stop()
else:
    df = load_demo_data()
    st.info(f"已生成 {len(df)} 期模拟数据（仅供演示）")

df = df.sort_values("期号").reset_index(drop=True)
all_numbers = list(range(1, 81))

# -----------------------------
# 通用坐标构建（2行×40列）
# -----------------------------
positions = {}
for num in range(1, 81):
    if num <= 40:
        row = 0
        col = num - 1
    else:
        row = 1
        col = num - 41
    positions[num] = (row, col)

# -----------------------------
# 1. 单期动画（交互式，下载HTML）
# -----------------------------
st.subheader("🎞️ 单期动画（2行×40列，可下载HTML）")
st.markdown("按时间顺序播放指定期数范围内每期的中奖号码。红色圆圈+白色数字表示中奖。")
anim_mode = st.radio("选择期数范围", ["最近N期", "自定义起止期号"], horizontal=True, key="anim_mode")
if anim_mode == "最近N期":
    n_anim = st.slider("选择最近多少期", min_value=5, max_value=min(200, len(df)), value=min(30, len(df)), key="n_anim")
    anim_df = df.tail(n_anim).copy().reset_index(drop=True)
else:
    all_issues = df["期号"].tolist()
    min_issue, max_issue = all_issues[0], all_issues[-1]
    start_issue = st.number_input("起始期号", min_value=int(min_issue), max_value=int(max_issue), value=int(min_issue), key="start_issue")
    end_issue = st.number_input("结束期号", min_value=int(min_issue), max_value=int(max_issue), value=int(max_issue), key="end_issue")
    if start_issue > end_issue:
        st.error("起始期号不能大于结束期号")
        anim_df = pd.DataFrame()
    else:
        anim_df = df[(df["期号"] >= start_issue) & (df["期号"] <= end_issue)].copy().reset_index(drop=True)

if len(anim_df) == 0:
    st.warning("请选择有效的期数范围")
else:
    frames = []
    for idx, row in anim_df.iterrows():
        period = row["期号"]
        win_nums = set(row["号码列表"])
        frame_data = []
        for num in range(1, 81):
            r, c = positions[num]
            is_win = num in win_nums
            frame_data.append({
                "期号": period,
                "号码": num,
                "中奖": is_win,
                "x": c,
                "y": r,
                "文本颜色": "white" if is_win else "#444444",
                "标记颜色": "red" if is_win else "lightgray",
                "标记大小": 25 if is_win else 20
            })
        frames.append(frame_data)

    import plotly.express as px
    all_frames = []
    for i, frame in enumerate(frames):
        for d in frame:
            d["frame"] = i
            all_frames.append(d)
    anim_df_long = pd.DataFrame(all_frames)

    fig_anim = px.scatter(
        anim_df_long,
        x="x", y="y", animation_frame="frame", text="号码",
        color="中奖", color_discrete_map={True: "red", False: "lightgray"},
        hover_data=["期号", "号码"],
        title="快乐8单期中奖动画（2行×40列）"
    )
    fig_anim.update_traces(textposition="middle center", textfont=dict(size=12), marker=dict(size=22, line=dict(width=1, color="darkred")))
    fig_anim.update_layout(
        xaxis=dict(title="列", tickmode='array', tickvals=list(range(0,41,5)), ticktext=[str(i+1) for i in range(0,41,5)], range=[-0.5,39.5]),
        yaxis=dict(title="行", tickmode='array', tickvals=[0,1], ticktext=["1-40","41-80"], range=[1.5,-0.5]),
        height=400
    )
    st.plotly_chart(fig_anim, use_container_width=True)
    anim_html = fig_anim.to_html(include_plotlyjs='cdn')
    st.download_button("📥 下载单期动画为HTML", data=anim_html, file_name="happy8_single_animation.html", mime="text/html")

    st.markdown("**📌 选择期号查看详细中奖号码**")
    period_options = anim_df["期号"].tolist()
    selected_period = st.selectbox("请选择期号", options=period_options, index=len(period_options)-1, key="single_anim_select")
    selected_row = anim_df[anim_df["期号"] == selected_period].iloc[0]
    win_numbers = sorted(selected_row["号码列表"])
    st.markdown(f"**期号：{selected_period}**")
    st.markdown(f"**中奖号码（共20个）**：{', '.join(map(str, win_numbers))}")

# -----------------------------
# 2. 3行滑动窗口视频（MP4）
# -----------------------------
st.subheader("🎥 3行滑动窗口视频（最新期在底部）")
st.markdown("使用最近 N 期数据，滑动窗口大小为3期，生成 MP4 视频。底部=最新期，颜色/背景渐变。")
if len(df) >= 3:
    col_v1, col_v2 = st.columns(2)
    with col_v1:
        video_mode = st.radio("选择期数范围", ["最近N期", "自定义起止期号"], key="video_mode")
    with col_v2:
        fps = st.number_input("视频帧率 (fps)", min_value=1, max_value=10, value=2, step=1)
    if video_mode == "最近N期":
        n_video = st.slider("选择最近多少期", min_value=3, max_value=min(200, len(df)), value=min(50, len(df)), key="n_video")
        start_idx = max(0, len(df) - n_video)
        video_df = df.iloc[start_idx:].reset_index(drop=True)
    else:
        all_issues = df["期号"].tolist()
        min_issue, max_issue = all_issues[0], all_issues[-1]
        v_start_issue = st.number_input("起始期号", min_value=int(min_issue), max_value=int(max_issue), value=int(min_issue), key="v_start_issue")
        v_end_issue = st.number_input("结束期号", min_value=int(min_issue), max_value=int(max_issue), value=int(max_issue), key="v_end_issue")
        if v_start_issue > v_end_issue:
            st.error("起始期号不能大于结束期号")
            video_df = pd.DataFrame()
        else:
            video_df = df[(df["期号"] >= v_start_issue) & (df["期号"] <= v_end_issue)].copy().reset_index(drop=True)
    if len(video_df) < 3:
        st.warning("选择的期数范围不足3期，无法生成视频。")
    else:
        if st.button("🚀 生成视频并下载"):
            with st.spinner("生成中，请稍候..."):
                with tempfile.TemporaryDirectory() as tmpdir:
                    windows = []
                    for i in range(len(video_df) - 2):
                        win = video_df.iloc[i:i+3]
                        windows.append(win)
                    total_frames = len(windows)
                    if total_frames == 0:
                        st.error("窗口数为0")
                    else:
                        # 画布参数
                        fig_width = 16.0
                        row_height = 0.23
                        total_rows = 3
                        title_space = 0.5
                        fig_height = total_rows * row_height + title_space
                        dpi = 100
                        target_w = int(fig_width * dpi)
                        target_h = int(fig_height * dpi)
                        if target_w % 2 != 0: target_w += 1
                        if target_h % 2 != 0: target_h += 1
                        fig_width = target_w / dpi
                        fig_height = target_h / dpi
                        ball_colors = [(220,20,60), (255,99,71), (255,182,193)]
                        bg_colors = ['#FFFFFF', '#FFFFFF', '#FFFFFF']
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        for idx, win in enumerate(windows):
                            fig, ax = plt.subplots(figsize=(fig_width, fig_height))
                            ax.set_xlim(-2, 80)
                            ax.set_ylim(0, 3)
                            ax.set_aspect('auto')
                            ax.axis('off')
                            y_bottoms = [0,1,2]
                            for row_idx in range(3):
                                rect = patches.Rectangle((0, y_bottoms[row_idx]), 80, 1, linewidth=0, facecolor=bg_colors[row_idx], alpha=0.5)
                                ax.add_patch(rect)
                            for num in range(1,81):
                                x = num - 1
                                for row_idx in range(3):
                                    y_center = y_bottoms[row_idx] + 0.5
                                    period_data = win.iloc[2 - row_idx]
                                    win_nums = set(period_data["号码列表"])
                                    is_win = num in win_nums
                                    if is_win:
                                        color_hex = '#{:02x}{:02x}{:02x}'.format(*ball_colors[row_idx])
                                        circle = plt.Circle((x, y_center), 0.32, color=color_hex, ec='none', zorder=2)
                                        ax.add_patch(circle)
                                        ax.text(x, y_center, str(num), ha='center', va='center', fontsize=8, color='white', weight='bold', zorder=3)
                                    else:
                                        circle = plt.Circle((x, y_center), 0.2, color='lightgray', ec='none', zorder=1)
                                        ax.add_patch(circle)
                                        ax.text(x, y_center, str(num), ha='center', va='center', fontsize=7, color='#444444', zorder=1)
                            for row_idx in range(3):
                                y_center = y_bottoms[row_idx] + 0.5
                                period_data = win.iloc[2 - row_idx]
                                period_text = f"{period_data['期号']}"
                                ax.text(-1.2, y_center, period_text, ha='center', va='center', fontsize=9, weight='bold')
                            ax.set_title(f"滑动窗口 {idx+1}/{total_frames} (最新期在底部)", fontsize=10, pad=5)
                            plt.tight_layout()
                            temp_path = os.path.join(tmpdir, f"temp_{idx+1:04d}.png")
                            plt.savefig(temp_path, dpi=dpi, bbox_inches='tight', facecolor='white')
                            plt.close(fig)
                            img = Image.open(temp_path)
                            w, h = img.size
                            new_w = w if w % 2 == 0 else w + 1
                            new_h = h if h % 2 == 0 else h + 1
                            if (new_w, new_h) != (w, h):
                                img = img.resize((new_w, new_h), Image.LANCZOS)
                            final_path = os.path.join(tmpdir, f"frame_{idx+1:04d}.png")
                            img.save(final_path)
                            os.remove(temp_path)
                            progress = (idx+1)/total_frames
                            progress_bar.progress(progress)
                            status_text.text(f"生成帧 {idx+1}/{total_frames}")
                        status_text.text("正在合成视频...")
                        output_video = os.path.join(tmpdir, "output.mp4")
                        cmd = ["ffmpeg", "-y", "-framerate", str(fps), "-i", os.path.join(tmpdir, "frame_%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", output_video]
                        try:
                            import subprocess
                            subprocess.run(cmd, check=True, capture_output=True, text=True)
                            with open(output_video, "rb") as f:
                                video_bytes = f.read()
                            st.success("视频生成成功！")
                            st.download_button("📥 下载视频 (MP4)", data=video_bytes, file_name="happy8_sliding_window.mp4", mime="video/mp4")
                        except Exception as e:
                            st.error(f"ffmpeg 合成失败: {e}")
else:
    st.warning("至少需要3期数据才能生成视频。")
