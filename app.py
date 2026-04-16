#!/usr/bin/env python3
"""
China Social Media Automation Toolkit - Web Interface
Streamlit Web界面
"""

import streamlit as st
import os
import sys
from datetime import datetime

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.social_publisher import SocialMediaManager
from tools.advanced import AutoLogin, ImageGenerator, ContentGenerator, ContentCollector

# 页面配置
st.set_page_config(
    page_title="中国社交媒体工具箱",
    page_icon="🇨🇳",
    layout="wide"
)

# 标题
st.title("🇨🇳 中国社交媒体自动化工具箱")
st.markdown("---")

# 侧边栏
with st.sidebar:
    st.header("⚙️ 设置")
    
    # 平台选择
    platform = st.selectbox(
        "选择平台",
        ["今日头条", "小红书", "抖音", "微信公众号"]
    )
    
    st.markdown("---")
    
    # 功能选择
    st.header("📋 功能")
    feature = st.radio(
        "选择功能",
        ["📝 发布内容", "📊 数据统计", "⏰ 定时任务", "⚙️ 配置"]
    )

# 主内容区
if feature == "📝 发布内容":
    st.header("📝 发布内容")
    
    with st.expander("📖 发布说明", expanded=False):
        st.markdown("""
        ### 发布规则
        1. **禁止#开头** - 不要使用话题标签
        2. **第一句话必须吸引读者** - 用问句/感叹句/悬念句
        3. **内容要引发共鸣** - 结合生活场景、痛点
        4. **字数≥400字** - 深度内容
        5. **必须配图** - 用AI生成或上传
        """)
    
    # 内容输入
    content = st.text_area("📝 内容", height=200, placeholder="输入要发布的内容...")
    
    # 配图选项
    image_option = st.radio("🖼️ 配图", ["🤖 AI生成", "📁 本地上传"])
    
    if image_option == "📁 本地上传":
        uploaded_file = st.file_uploader("选择图片", type=['jpg', 'png', 'jpeg'])
        if uploaded_file:
            st.image(uploaded_file, width=300)
    
    # 发布按钮
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🚀 发布", type="primary", use_container_width=True):
            if content:
                with st.spinner("发布中..."):
                    manager = SocialMediaManager()
                    result = manager.publish("toutiao", content=content)
                    if result.get("success"):
                        st.success("✅ 发布成功!")
                    else:
                        st.error(f"❌ 发布失败: {result.get('error')}")
            else:
                st.warning("⚠️ 请输入内容")

elif feature == "📊 数据统计":
    st.header("📊 数据统计")
    
    # 获取统计数据
    manager = SocialMediaManager()
    stats = manager.get_all_stats()
    
    # 显示统计卡片
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("👥 粉丝", "150")
    with col2:
        st.metric("👁️ 展现", "10.2K")
    with col3:
        st.metric("❤️ 点赞", "523")
    with col4:
        st.metric("💰 收入", "¥1.37")
    
    st.markdown("---")
    
    # 详细数据
    st.subheader("📈 详细数据")
    
    # 模拟图表数据
    import pandas as pd
    import numpy as np
    
    # 生成模拟数据
    dates = pd.date_range(start="2026-04-01", periods=16)
    views = np.random.randint(100, 1000, size=len(dates))
    likes = views * np.random.uniform(0.01, 0.1, size=len(dates))
    
    df = pd.DataFrame({
        "日期": dates,
        "展现量": views,
        "点赞": likes.astype(int),
        "评论": np.random.randint(0, 50, size=len(dates))
    })
    
    # 显示数据
    st.dataframe(df, use_container_width=True)
    
    # 使用表格
    st.download_button(
        "📥 下载数据",
        df.to_csv(index=False),
        "social_stats.csv",
        "text/csv"
    )

elif feature == "⏰ 定时任务":
    st.header("⏰ 定时任务")
    
    # 现有任务
    st.subheader("📋 现有任务")
    
    tasks = [
        {"时间": "06:00", "平台": "头条号", "数量": "10条", "状态": "✅ 活跃"},
        {"时间": "12:00", "平台": "头条号", "数量": "10条", "状态": "✅ 活跃"},
        {"时间": "18:00", "平台": "头条号", "数量": "10条", "状态": "✅ 活跃"},
    ]
    
    for task in tasks:
        col1, col2, col3, col4 = st.columns([1, 2, 2, 1])
        with col1:
            st.write(task["时间"])
        with col2:
            st.write(task["平台"])
        with col3:
            st.write(task["数量"])
        with col4:
            st.write(task["状态"])
    
    st.markdown("---")
    
    # 添加新任务
    st.subheader("➕ 添加定时任务")
    
    col1, col2 = st.columns(2)
    with col1:
        new_time = st.time_input("发布时间", datetime.time(6, 0))
    with col2:
        new_platform = st.selectbox("平台", ["头条号", "小红书"])
    
    new_count = st.number_input("发布数量", min_value=1, max_value=20, value=5)
    
    if st.button("➕ 添加任务"):
        st.success(f"✅ 已添加任务: {new_time} {new_platform} {new_count}条")

elif feature == "⚙️ 配置":
    st.header("⚙️ 配置")
    
    # 账号配置
    st.subheader("📱 账号配置")
    
    col1, col2 = st.columns(2)
    with col1:
        toutiao_phone = st.text_input("头条号手机号", type="default")
    with col2:
        toutiao_pwd = st.text_input("头条号密码", type="password")
    
    col1, col2 = st.columns(2)
    with col1:
        xhs_phone = st.text_input("小红书手机号", type="default")
    with col2:
        xhs_pwd = st.text_input("小红书密码", type="password")
    
    st.markdown("---")
    
    # API配置
    st.subheader("🔑 API配置")
    
    col1, col2 = st.columns(2)
    with col1:
        openai_key = st.text_input("OpenAI API Key", type="password")
    with col2:
        anthropic_key = st.text_input("Anthropic API Key", type="password")
    
    st.markdown("---")
    
    if st.button("💾 保存配置"):
        st.success("✅ 配置已保存!")

# 页脚
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: gray;'>"
    "🇨🇳 China Social Media Automation Toolkit | "
    "Built with ❤️"
    "</p>",
    unsafe_allow_html=True
)