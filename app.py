#!/usr/bin/env python3
"""
完整功能的Bittensor子网模拟器Web界面
包含多策略对比、高级图表、触发倍数分析等所有功能
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import json
import os
import sys
import tempfile
import zipfile
from datetime import datetime
from decimal import Decimal
import logging
import time

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.simulation.simulator import BittensorSubnetSimulator
from src.strategies.tempo_sell_strategy import TempoSellStrategy, StrategyPhase

# 配置页面
st.set_page_config(
    page_title="Bittensor成熟子网市值管理模拟器",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #2a5298;
    }
    .success-box {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .warning-box {
        background: #fff3cd;
        border: 1px solid #ffeaa7;
        color: #856404;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

class FullWebInterface:
    """完整功能的Web界面"""
    
    def __init__(self):
        # 初始化session state
        if 'simulation_results' not in st.session_state:
            st.session_state.simulation_results = {}
        if 'simulation_running' not in st.session_state:
            st.session_state.simulation_running = False
    
    def render_header(self):
        """渲染页面头部"""
        st.markdown("""
        <div class="main-header">
            <h1>💰 Bittensor成熟子网市值管理模拟器</h1>
            <p>专业的成熟子网市值管理、投资策略优化和风险分析工具</p>
        </div>
        """, unsafe_allow_html=True)
    
    def render_sidebar_config(self):
        """渲染完整配置面板"""
        st.sidebar.header("📊 模拟配置")
        
        # 基础模拟参数
        st.sidebar.subheader("🔧 基础参数")
        
        simulation_days = st.sidebar.slider(
            "模拟天数", 
            min_value=1, 
            max_value=360,
            value=60,
            help="模拟的总天数，建议60-180天"
        )
        
        # 🔧 新增：TAO产生速率配置
        tao_per_block = st.sidebar.selectbox(
            "TAO产生速率（每区块）",
            options=[
                ("1.0", "🔥 标准排放（1.0 TAO/区块）"),
                ("0.5", "⚡ 减半排放（0.5 TAO/区块）"),
                ("0.25", "🛡️ 超低排放（0.25 TAO/区块）"),
                ("2.0", "🚀 双倍排放（2.0 TAO/区块）")
            ],
            index=0,  # 默认选择标准排放
            format_func=lambda x: x[1],
            help="控制网络每个区块产生的TAO数量，影响总排放量和市场流动性"
        )[0]
        
        # 添加移动平均alpha参数
        moving_alpha = st.sidebar.slider(
            "α_base（基准Alpha系数）",
            min_value=0.0001,
            max_value=0.2,
            value=0.0003,
            step=0.0001,
            format="%.4f",
            help="EMA公式中的基准Alpha系数：α(t) = α_base × (t / (t + T_half))。链上验证值为0.0003，较小值价格更稳定，较大值收敛更快"
        )
        
        # 显示TAO产生速率的影响说明
        tao_rate = float(tao_per_block)
        daily_tao_production = tao_rate * 7200  # 每天7200个区块
        yearly_tao_production = daily_tao_production * 365
        
        st.sidebar.info(f"""
        **💡 TAO产生速率影响**  
        • 每区块产生: {tao_rate} TAO  
        • 每日总产生: {daily_tao_production:,.0f} TAO  
        • 年度总产生: {yearly_tao_production:,.0f} TAO  
        • 影响: 子网TAO注入量、流动性
        """)
        
        # 成熟子网配置
        st.sidebar.subheader("🏗️ 成熟子网配置")
        
        # 快速配置选项
        config_mode = st.sidebar.radio(
            "配置方式",
            ["使用默认模板", "手动配置参数", "TaoStats URL导入"],
            help="选择配置成熟子网参数的方式"
        )
        
        if config_mode == "使用默认模板":
            # 默认模板参数（基于实际子网数据）
            amm_pool_dtao = 373070  # 373.07K dTAO
            amm_pool_tao = 560.47   # 560.47 TAO
            circulating_supply = 768040  # 768.04K dTAO
            daily_sell_pressure = 1.0  # 1%
            
            st.sidebar.success("""
            **✅ 默认模板已加载**
            • AMM池: 373.07K dTAO + 560.47 TAO
            • 流通量: 768.04K dTAO  
            • 启动时间: 约2个月
            • 默认抛压: 1%/天
            """)
            
        elif config_mode == "手动配置参数":
            col1, col2 = st.sidebar.columns(2)
            with col1:
                amm_pool_dtao = st.number_input(
                    "AMM池dTAO数量 (K)", 
                    value=373.07, 
                    min_value=1.0,
                    step=1.0,
                    help="当前AMM池中的dTAO数量（千）"
                ) * 1000
                
                amm_pool_tao = st.number_input(
                    "AMM池TAO数量", 
                    value=560.47, 
                    min_value=0.1,
                    step=0.1,
                    help="当前AMM池中的TAO数量"
                )
            
            with col2:
                circulating_supply = st.number_input(
                    "dTAO流通量 (K)", 
                    value=768.04, 
                    min_value=1.0,
                    step=1.0,
                    help="当前dTAO总流通量（千）"
                ) * 1000
                
                daily_sell_pressure = st.slider(
                    "日常抛压比例 (%)", 
                    min_value=0.0, 
                    max_value=10.0,
                    value=1.0,
                    step=0.1,
                    help="池外dTAO每日抛售比例"
                )
        
        else:  # TaoStats URL导入
            taostats_url = st.sidebar.text_input(
                "TaoStats链接",
                placeholder="https://taostats.io/subnets/XX/chart",
                help="粘贴TaoStats子网页面链接自动导入参数"
            )
            
            if taostats_url:
                st.sidebar.info("🔄 URL解析功能开发中...")
                # TODO: 实现URL解析逻辑
                # 暂时使用默认值
                amm_pool_dtao = 373070
                amm_pool_tao = 560.47
                circulating_supply = 768040
                daily_sell_pressure = 1.0
            else:
                # 默认值
                amm_pool_dtao = 373070
                amm_pool_tao = 560.47
                circulating_supply = 768040
                daily_sell_pressure = 1.0
        
        # 计算启动时间（反推逻辑）
        estimated_days = (circulating_supply / 14400) - 2.5  # 减去前5天修正系数
        estimated_days = max(0, estimated_days)
        
        # 计算池外流动dTAO
        external_dtao = circulating_supply - amm_pool_dtao
        
        # 显示计算结果
        st.sidebar.info(f"""
        **📊 自动计算结果**  
        • 预估启动时间: {estimated_days:.1f} 天前
        • 池外流动dTAO: {external_dtao/1000:.1f}K  
        • 每日抛压量: {(external_dtao * daily_sell_pressure / 100)/1000:.1f}K dTAO
        • 当前dTAO价格比例: {amm_pool_dtao/(amm_pool_dtao+amm_pool_tao)*100:.1f}%
        """)
        
        # 将新子网的初始参数设置为成熟子网状态
        initial_dtao = amm_pool_dtao  # 已经是实际数量，不需要除以K
        initial_tao = amm_pool_tao
        
        # 市场参数
        st.sidebar.subheader("📈 市场参数")
        
        other_subnets_total_moving_price = st.sidebar.slider(
            "其他子网合计移动价格", 
            min_value=0.5, 
            max_value=10.0,
            value=1.4, 
            step=0.1,
            help="所有其他子网的dTAO移动价格总和"
        )
        
        # 策略参数
        st.sidebar.subheader("💰 策略参数")
        
        total_budget = st.sidebar.number_input(
            "总预算（TAO）", 
            value=1000.0, 
            min_value=100.0,
            max_value=10000.0,
            step=100.0
        )
        
        # 添加策略开始时间配置 - 支持天数和区块数双重输入
        st.sidebar.subheader("⏰ 策略开始时间")
        
        # 计算最大值（基于模拟天数）
        max_blocks = simulation_days * 7200
        max_days = simulation_days
        
        # 创建两列布局
        col1, col2 = st.sidebar.columns(2)
        
        with col1:
            strategy_start_delay_days = st.number_input(
                "延迟天数",
                value=0.0,
                min_value=0.0,
                max_value=float(max_days),
                step=0.1,
                format="%.1f",
                help="策略开始买入的延迟天数",
                key="strategy_delay_days"
            )
        
        with col2:
            # 根据天数计算对应的区块数
            calculated_blocks = int(strategy_start_delay_days * 7200)
            strategy_start_delay_blocks = st.number_input(
                "延迟区块数",
                value=max(1, calculated_blocks),
                min_value=1,
                max_value=max_blocks,
                step=1,
                help="策略开始买入的延迟区块数",
                key="strategy_delay_blocks"
            )
        
        # 如果用户修改了区块数，反向计算天数
        if strategy_start_delay_blocks != calculated_blocks and strategy_start_delay_blocks > 0:
            calculated_days = strategy_start_delay_blocks / 7200
            if abs(calculated_days - strategy_start_delay_days) > 0.01:  # 避免无限循环
                st.session_state.strategy_delay_days = calculated_days
                st.rerun()
        
        # 使用区块数作为最终值
        strategy_start_delay = strategy_start_delay_blocks
        
        # 显示换算信息
        st.sidebar.info(f"""
        **⏰ 时间换算**  
        • {strategy_start_delay_days:.1f} 天 = {strategy_start_delay_blocks:,} 区块  
        • 每天 = 7,200 区块 (每12秒1个区块)  
        • 最大延迟: {max_days} 天 ({max_blocks:,} 区块)
        """)
        
        # 成熟子网无注册成本，隐藏UI
        registration_cost = 0
        
        buy_threshold = st.sidebar.slider(
            "买入阈值", 
            min_value=0.1, 
            max_value=2.0, 
            value=0.3, 
            step=0.05,
            help="dTAO价格低于此值时触发买入"
        )
        
        buy_step_size = st.sidebar.slider(
            "买入步长 (TAO)", 
            min_value=0.05, 
            max_value=5.0, 
            value=0.5, 
            step=0.05,
            help="每次买入的TAO数量"
        )
        
        # 重点：触发倍数配置
        st.sidebar.subheader("🔥 大量卖出触发配置")
        
        mass_sell_trigger_multiplier = st.sidebar.slider(
            "触发倍数",
            min_value=1.2,
            max_value=5.0,
            value=3.0,  # 🔧 修改默认值为3倍
            step=0.1,
            help="当AMM池TAO储备达到初始储备的指定倍数时触发大量卖出"
        )
        
        # 显示策略类型
        if mass_sell_trigger_multiplier <= 1.5:
            st.sidebar.success("🚀 激进策略：更早获利，但风险较高")
        elif mass_sell_trigger_multiplier <= 2.5:
            st.sidebar.info("⚖️ 平衡策略：适中的风险和收益")
        else:
            st.sidebar.warning("🛡️ 保守策略：更晚获利，但更稳妥")
        
        reserve_dtao = st.sidebar.number_input(
            "保留dTAO数量",
            min_value=100.0,
            max_value=10000.0,
            value=5000.0,
            step=100.0,
            help="大量卖出时保留的dTAO数量"
        )
        
        # 新增参数
        user_reward_share = st.sidebar.slider(
            "我的奖励份额 (%)",
            min_value=0.0,
            max_value=100.0,
            value=59.0,
            step=1.0,
            format="%.1f%%",
            help="模拟您能获得子网dTAO总奖励的百分比。剩余部分将被视为外部参与者的奖励。"
        )
        
        external_sell_pressure = st.sidebar.slider(
            "外部卖出压力 (%)",
            min_value=0.0,
            max_value=100.0,
            value=100.0, # 默认100%，模拟Root验证者等外部参与者全部抛售
            step=1.0,
            help="外部参与者在获得dTAO奖励后，立即将其卖出为TAO的比例。用于模拟市场抛压。"
        )
        
        # 二次增持策略配置
        st.sidebar.subheader("🔄 二次增持策略")
        
        enable_second_buy = st.sidebar.checkbox(
            "启用二次增持",
            value=False,
            help="勾选启用二次增持功能，可在指定时间后追加投资"
        )
        
        # 只有启用时才显示配置参数
        if enable_second_buy:
            second_buy_delay_days = st.sidebar.number_input(
                "延迟天数",
                min_value=0,
                max_value=360,
                value=1,  # 🔧 修改默认值为1天
                step=1,
                help="从首次买入后延迟多少天进行二次增持。设为0表示在免疫期结束后立即执行。"
            )

            second_buy_tao_amount = st.sidebar.number_input(
                "增持金额 (TAO)",
                min_value=100.0,
                max_value=10000.0,
                value=1000.0,  # 🔧 修改默认值为1000 TAO
                step=100.0,
                help="第二次投入的TAO数量"
            )
        else:
            second_buy_delay_days = 0
            second_buy_tao_amount = 0.0

        run_button = st.sidebar.button("🚀 运行模拟", use_container_width=True, type="primary")
        
        # 构建配置
        config = {
            "simulation": {
                "days": simulation_days,
                "blocks_per_day": 7200,
                "tempo_blocks": 360,
                "tao_per_block": tao_per_block,
                "moving_alpha": str(moving_alpha)
            },
            "subnet": {
                "initial_dtao": str(initial_dtao),
                "initial_tao": str(initial_tao),
                "immunity_blocks": 0,  # 成熟子网无免疫期
                "moving_alpha": str(moving_alpha),
                "halving_time": 201600,
                # 成熟子网特有参数
                "circulating_supply": str(circulating_supply),
                "estimated_startup_days": str(estimated_days),
                "is_mature_subnet": True
            },
            "market": {
                "other_subnets_avg_price": str(other_subnets_total_moving_price),
                "daily_sell_pressure": str(daily_sell_pressure),
                "external_dtao_amount": str(external_dtao)
            },
            "strategy": {
                "total_budget_tao": str(total_budget),
                "registration_cost_tao": str(registration_cost),
                "buy_threshold_price": str(buy_threshold),
                "buy_step_size_tao": str(buy_step_size),
                "sell_multiplier": "2.0",
                "sell_trigger_multiplier": str(mass_sell_trigger_multiplier),
                "reserve_dtao": str(reserve_dtao),
                "sell_delay_blocks": 2,
                "user_reward_share": str(user_reward_share),
                "external_sell_pressure": str(external_sell_pressure),
                "second_buy_delay_blocks": second_buy_delay_days * 7200,
                "second_buy_tao_amount": str(second_buy_tao_amount),
                "immunity_period": int(strategy_start_delay)
            }
        }
        
        return {
            'config': config,
            'run_button': run_button
        }
    
    def create_price_chart(self, data: pd.DataFrame) -> go.Figure:
        """创建价格走势图"""
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=['价格走势', '投资回报率'],
            vertical_spacing=0.15
        )
        
        # 计算天数
        data['day'] = data['block_number'] / 7200.0
        
        # 价格图表
        fig.add_trace(go.Scatter(
            x=data['day'],
            y=data['spot_price'],
            name='现货价格',
            line=dict(color='red', width=2)
        ), row=1, col=1)
        
        fig.add_trace(go.Scatter(
            x=data['day'],
            y=data['moving_price'],
            name='移动价格',
            line=dict(color='blue', width=2, dash='dash')
        ), row=1, col=1)
        
        # 🔧 修正：计算ROI，使用当前市场价格计算总资产价值
        total_value = (data['strategy_tao_balance'] + 
                      data['strategy_dtao_balance'] * data['spot_price'])  # 使用spot_price
        # 🔧 修正：获取实际的总投资金额（包括二次增持）
        # 注意：这里需要从配置中获取实际的总投资，而不是从余额推算
        # 暂时使用传统方法，但会在后续优化中改进
        first_row_balance = float(data.iloc[0]['strategy_tao_balance'])
        registration_cost = 0  # 成熟子网无注册成本，不显示此项
        # 这里需要从策略配置中获取二次增持金额，暂时先使用估算
        roi_values = (total_value / first_row_balance - 1) * 100
        
        fig.add_trace(go.Scatter(
            x=data['day'],
            y=roi_values,
            name='ROI (%)',
            line=dict(color='green', width=2)
        ), row=2, col=1)
        
        fig.update_layout(
            title="价格分析与投资回报",
            template='plotly_white',
            height=600
        )
        
        fig.update_xaxes(title_text="天数", row=1, col=1)
        fig.update_xaxes(title_text="天数", row=2, col=1)
        fig.update_yaxes(title_text="价格 (TAO)", row=1, col=1)
        fig.update_yaxes(title_text="ROI (%)", row=2, col=1)
        
        return fig
    
    def create_reserves_chart(self, data: pd.DataFrame) -> go.Figure:
        """创建AMM池储备图表"""
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=['dTAO储备变化', 'TAO储备变化'],
            vertical_spacing=0.15
        )
        
        # 计算天数
        data['day'] = data['block_number'] / 7200.0
        
        # dTAO储备
        fig.add_trace(go.Scatter(
            x=data['day'],
            y=data['dtao_reserves'],
            name='dTAO储备',
            line=dict(color='green', width=2),
            fill='tonexty'
        ), row=1, col=1)
        
        # TAO储备
        fig.add_trace(go.Scatter(
            x=data['day'],
            y=data['tao_reserves'],
            name='TAO储备',
            line=dict(color='red', width=2),
            fill='tonexty'
        ), row=2, col=1)
        
        fig.update_layout(
            title="AMM池储备变化",
            template='plotly_white',
            height=600
        )
        
        fig.update_xaxes(title_text="天数", row=1, col=1)
        fig.update_xaxes(title_text="天数", row=2, col=1)
        fig.update_yaxes(title_text="dTAO数量", row=1, col=1)
        fig.update_yaxes(title_text="TAO数量", row=2, col=1)
        
        return fig
    
    def create_emission_chart(self, data: pd.DataFrame) -> go.Figure:
        """创建排放分析图表"""
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=['排放份额变化', 'TAO注入量'],
            vertical_spacing=0.15
        )
        
        # 计算天数
        data['day'] = data['block_number'] / 7200.0
        
        # 排放份额
        fig.add_trace(go.Scatter(
            x=data['day'],
            y=data['emission_share'] * 100,
            name='排放份额(%)',
            line=dict(color='purple', width=2),
            fill='tonexty'
        ), row=1, col=1)
        
        # TAO注入量（累积）
        cumulative_injection = data['tao_injected'].cumsum()
        fig.add_trace(go.Scatter(
            x=data['day'],
            y=cumulative_injection,
            name='累积TAO注入',
            line=dict(color='brown', width=2)
        ), row=2, col=1)
        
        fig.update_layout(
            title="排放分析",
            template='plotly_white',
            height=600
        )
        
        fig.update_xaxes(title_text="天数", row=1, col=1)
        fig.update_xaxes(title_text="天数", row=2, col=1)
        fig.update_yaxes(title_text="排放份额(%)", row=1, col=1)
        fig.update_yaxes(title_text="累积TAO注入量", row=2, col=1)
        
        return fig
    
    def create_investment_chart(self, data: pd.DataFrame) -> go.Figure:
        """创建投资分析图表"""
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=['资产组合变化', '交易活动'],
            vertical_spacing=0.15
        )
        
        # 计算天数
        data['day'] = data['block_number'] / 7200.0
        
        # 资产组合
        fig.add_trace(go.Scatter(
            x=data['day'],
            y=data['strategy_tao_balance'],
            name='TAO余额',
            line=dict(color='orange', width=2)
        ), row=1, col=1)
        
        # 🔧 修正：dTAO余额（按当前市场价格计算TAO等值）
        dtao_value = data['strategy_dtao_balance'] * data['spot_price']  # 使用spot_price而不是固定价格
        fig.add_trace(go.Scatter(
            x=data['day'],
            y=dtao_value,
            name='dTAO价值 (TAO等值)',
            line=dict(color='lightblue', width=2)
        ), row=1, col=1)
        
        # 🔧 修正：总资产价值（使用正确的dTAO价值计算）
        total_value = data['strategy_tao_balance'] + dtao_value
        fig.add_trace(go.Scatter(
            x=data['day'],
            y=total_value,
            name='总资产价值',
            line=dict(color='darkgreen', width=3)
        ), row=1, col=1)
        
        # Pending emission显示
        fig.add_trace(go.Scatter(
            x=data['day'],
            y=data['pending_emission'],
            name='待分配排放',
            line=dict(color='red', width=2, dash='dot')
        ), row=2, col=1)
        
        fig.update_layout(
            title="投资分析",
            template='plotly_white',
            height=600
        )
        
        fig.update_xaxes(title_text="天数", row=1, col=1)
        fig.update_xaxes(title_text="天数", row=2, col=1)
        fig.update_yaxes(title_text="价值 (TAO)", row=1, col=1)
        fig.update_yaxes(title_text="待分配排放 (dTAO)", row=2, col=1)
        
        return fig
    
    def run_simulation(self, config, scenario_name="默认场景"):
        """运行模拟"""
        try:
            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                # 保存配置文件
                config_path = os.path.join(temp_dir, "config.json")
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                
                # 创建模拟器
                simulator = BittensorSubnetSimulator(config_path, temp_dir)
                
                # 创建进度条
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # 运行模拟
                def progress_callback(progress, block, result):
                    progress_bar.progress(progress / 100)
                    if block % 500 == 0:
                        status_text.text(f"模拟进行中... 第{block//7200:.1f}天 (区块 {block}/{simulator.total_blocks})")
                
                # 运行模拟
                summary = simulator.run_simulation(progress_callback)
                
                # 清理进度条
                progress_bar.empty()
                status_text.empty()
                
                # 获取区块数据
                block_data = pd.DataFrame(simulator.block_data)
                
                # 保存结果
                result = {
                    'config': config,
                    'summary': summary,
                    'block_data': block_data,
                    'scenario_name': scenario_name
                }
                
                return result
                
        except Exception as e:
            st.error(f"模拟运行失败: {e}")
            return None
    
    def render_simulation_results(self, result):
        """渲染模拟结果"""
        if not result:
            return
        
        summary = result['summary']
        block_data = result['block_data']
        scenario_name = result['scenario_name']
        
        st.header(f"📊 模拟结果 - {scenario_name}")
        
        # 关键指标
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            roi_value = summary['key_metrics']['total_roi']
            roi_delta = "正收益" if roi_value > 0 else "亏损"
            st.metric(
                "最终ROI",
                f"{roi_value:.2f}%",
                delta=roi_delta,
                help="总投资回报率"
            )
        
        with col2:
            final_price = summary['final_pool_state']['final_price']
            initial_price = 1.0  # 初始价格1:1
            price_change = ((float(final_price) - initial_price) / initial_price) * 100
            st.metric(
                "最终价格",
                f"{final_price:.4f} TAO",
                delta=f"{price_change:+.1f}%",
                help="dTAO的最终价格"
            )
        
        with col3:
            total_volume = summary['final_pool_state']['total_volume']
            st.metric(
                "总交易量",
                f"{total_volume:.2f} dTAO",
                help="累计交易量"
            )
        
        with col4:
            tao_injected = summary['final_pool_state']['total_tao_injected']
            st.metric(
                "TAO注入总量",
                f"{tao_injected:.2f} TAO",
                help="累计注入的TAO数量"
            )
        
        # 图表展示
        st.subheader("📈 详细分析图表")
        
        # 创建选项卡
        chart_tab1, chart_tab2, chart_tab3, chart_tab4 = st.tabs([
            "💰 价格与ROI", "🏦 AMM池储备", "📊 排放分析", "📈 投资组合"
        ])
        
        with chart_tab1:
            price_fig = self.create_price_chart(block_data)
            st.plotly_chart(price_fig, use_container_width=True)
        
        with chart_tab2:
            reserves_fig = self.create_reserves_chart(block_data)
            st.plotly_chart(reserves_fig, use_container_width=True)
        
        with chart_tab3:
            emission_fig = self.create_emission_chart(block_data)
            st.plotly_chart(emission_fig, use_container_width=True)
        
        with chart_tab4:
            investment_fig = self.create_investment_chart(block_data)
            st.plotly_chart(investment_fig, use_container_width=True)
        
        # 策略分析
        st.subheader("🎯 策略执行分析")
        
        # 🔧 修正：计算策略表现指标，使用当前市场价格
        final_tao = float(block_data.iloc[-1]['strategy_tao_balance'])
        final_dtao = float(block_data.iloc[-1]['strategy_dtao_balance'])
        final_price_val = float(block_data.iloc[-1]['spot_price'])  # 使用实际的最终市场价格
        total_asset_value = final_tao + (final_dtao * final_price_val)  # 正确的总资产计算
        
        budget = float(result['config']['strategy']['total_budget_tao'])
        registration_cost = float(result['config']['strategy']['registration_cost_tao'])
        second_buy_amount = float(result['config']['strategy']['second_buy_tao_amount'])
        
        # 🔧 修正：计算实际总投资
        actual_total_investment = budget + second_buy_amount
        
        analysis_col1, analysis_col2 = st.columns(2)
        
        with analysis_col1:
            st.info(f"""
            **📊 资产明细**
            - TAO余额: {final_tao:.2f} TAO
            - dTAO余额: {final_dtao:.2f} dTAO
            - dTAO市价: {final_price_val:.4f} TAO/dTAO
            - dTAO价值: {final_dtao * final_price_val:.2f} TAO
            - 总资产价值: {total_asset_value:.2f} TAO
            """)
        
        with analysis_col2:
            # 🔧 修正：基于实际总投资计算收益
            net_profit = total_asset_value - actual_total_investment
            roi_percentage = (net_profit/actual_total_investment)*100 if actual_total_investment > 0 else 0
            st.success(f"""
            **💰 收益分析**
            - 初始预算: {budget:.2f} TAO
            - 二次增持: {second_buy_amount:.2f} TAO
            - 总投资: {actual_total_investment:.2f} TAO
            - 注册成本: 已禁用（成熟子网）
            - 净收益: {net_profit:.2f} TAO
            - ROI: {roi_percentage:.2f}%
            """)
        
        # --- Key Metrics ---
        st.subheader("核心指标")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("最终总资产 (TAO)", f"{summary['key_metrics']['final_asset_value']:.2f}")
        col2.metric("净回报率 (ROI)", f"{summary['key_metrics']['total_roi']:.2%}")
        col3.metric("最终dTAO价格 (TAO)", f"{summary['final_pool_state']['final_price']:.6f}")
        # 新增指标卡 - 修复策略阶段显示
        try:
            final_phase_value = summary['strategy_performance']['strategy_phase']
            if isinstance(final_phase_value, int):
                final_phase_name = StrategyPhase(final_phase_value).name
            elif hasattr(final_phase_value, 'name'):
                final_phase_name = final_phase_value.name
            else:
                final_phase_name = str(final_phase_value)
        except (KeyError, ValueError):
            final_phase_name = "未知"
        col4.metric("最终策略阶段", final_phase_name)
    
    def render_comparison_tools(self):
        """渲染多策略对比工具"""
        st.header("🔄 多策略对比分析")
        
        if len(st.session_state.simulation_results) < 1:
            st.info("请先运行至少一个模拟场景")
            return
        
        # 创建对比类型选择
        comparison_type = st.selectbox(
            "🎯 选择对比类型",
            options=[
                ("multiplier", "🔥 触发倍数对比"),
                ("tao_emission", "⚡ TAO产生速率对比"),
                ("threshold", "💰 买入阈值对比")
            ],
            format_func=lambda x: x[1]
        )[0]
        
        if comparison_type == "tao_emission":
            # TAO产生速率对比
            st.subheader("⚡ TAO产生速率影响对比")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                base_days = st.number_input("模拟天数", value=30, min_value=7, max_value=180, key="tao_days")
            with col2:
                base_budget = st.number_input("预算(TAO)", value=1000, min_value=100, max_value=5000, key="tao_budget")
            with col3:
                base_multiplier = st.slider("触发倍数", 1.2, 4.0, 2.0, 0.1, key="tao_multiplier")
            
            if st.button("🚀 运行TAO产生速率对比", type="primary"):
                self.run_tao_emission_comparison(base_days, base_budget, base_multiplier)
        
        elif comparison_type == "multiplier":
            # 快速对比工具
            st.subheader("⚡ 快速对比不同触发倍数")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                base_days = st.number_input("模拟天数", value=30, min_value=7, max_value=180)
            with col2:
                base_budget = st.number_input("预算(TAO)", value=1000, min_value=100, max_value=5000)
            with col3:
                base_threshold = st.slider("买入阈值", 0.1, 1.0, 0.3, 0.05)
            
            if st.button("🚀 运行触发倍数对比", type="primary"):
                self.run_multiplier_comparison(base_days, base_budget, base_threshold)
        
        elif comparison_type == "threshold":
            # 买入阈值对比
            st.subheader("💰 买入阈值影响对比")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                base_days = st.number_input("模拟天数", value=30, min_value=7, max_value=180, key="thresh_days")
            with col2:
                base_budget = st.number_input("预算(TAO)", value=1000, min_value=100, max_value=5000, key="thresh_budget")
            with col3:
                base_multiplier = st.slider("触发倍数", 1.2, 4.0, 2.0, 0.1, key="thresh_multiplier")
            
            if st.button("🚀 运行买入阈值对比", type="primary"):
                self.run_threshold_comparison(base_days, base_budget, base_multiplier)
        
        # 现有结果对比
        if len(st.session_state.simulation_results) >= 2:
            st.subheader("📊 已有结果对比")
            
            scenarios = list(st.session_state.simulation_results.keys())
            selected_scenarios = st.multiselect(
                "选择要对比的场景",
                scenarios,
                default=scenarios[-2:] if len(scenarios) >= 2 else scenarios
            )
            
            if len(selected_scenarios) >= 2:
                self.render_scenario_comparison(selected_scenarios)
    
    def run_tao_emission_comparison(self, days, budget, multiplier):
        """运行TAO产生速率对比"""
        tao_rates = [
            ("0.25", "🛡️ 超低排放"),
            ("0.5", "⚡ 减半排放"),
            ("1.0", "🔥 标准排放"),
            ("2.0", "🚀 双倍排放")
        ]
        comparison_results = {}
        
        progress_container = st.container()
        
        for i, (rate, desc) in enumerate(tao_rates):
            with progress_container:
                st.info(f"正在测试 {desc} ({rate} TAO/区块)... ({i+1}/{len(tao_rates)})")
            
            # 创建配置
            config = {
                "simulation": {
                    "days": days,
                    "blocks_per_day": 7200,
                    "tempo_blocks": 360,
                    "tao_per_block": rate  # 🔧 关键：不同的TAO产生速率
                },
                "subnet": {
                    "initial_dtao": "1",
                    "initial_tao": "1",
                    "immunity_blocks": 7200,
                    "moving_alpha": "0.1",
                    "halving_time": 201600
                },
                "market": {
                    "other_subnets_avg_price": "2.0"
                },
                "strategy": {
                    "total_budget_tao": str(budget),
                    "registration_cost_tao": "300",
                    "buy_threshold_price": "0.3",
                    "buy_step_size_tao": "0.5",
                    "sell_multiplier": "2.0",
                    "sell_trigger_multiplier": str(multiplier),
                    "reserve_dtao": "5000",
                    "sell_delay_blocks": 2
                }
            }
            
            # 运行模拟（不显示进度条）
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    config_path = os.path.join(temp_dir, "config.json")
                    with open(config_path, 'w') as f:
                        json.dump(config, f)
                    
                    simulator = BittensorSubnetSimulator(config_path, temp_dir)
                    summary = simulator.run_simulation()
                    
                    scenario_name = f"TAO产生{rate}/区块"
                    comparison_results[scenario_name] = {
                        'config': config,
                        'summary': summary,
                        'block_data': pd.DataFrame(simulator.block_data),
                        'scenario_name': scenario_name,
                        'tao_rate': float(rate),
                        'description': desc
                    }
                    
            except Exception as e:
                st.error(f"测试 {desc} 失败: {e}")
        
        progress_container.empty()
        
        if comparison_results:
            # 显示对比结果
            self.display_tao_emission_comparison(comparison_results)
    
    def display_tao_emission_comparison(self, results):
        """显示TAO产生速率对比结果"""
        st.success("🎉 TAO产生速率对比完成！")
        
        # 创建对比表格
        comparison_data = []
        for scenario_name, result in results.items():
            summary = result['summary']
            tao_rate = result['tao_rate']
            desc = result['description']
            
            # 计算关键指标
            daily_emission = tao_rate * 7200  # 每日TAO产生量
            
            comparison_data.append({
                'TAO产生速率': f"{desc} ({tao_rate}/区块)",
                '日产生量': f"{daily_emission:,.0f} TAO",
                'ROI (%)': f"{summary['key_metrics']['total_roi']:.2f}",
                '最终价格 (TAO)': f"{summary['final_pool_state']['final_price']:.4f}",
                'TAO注入总量': f"{summary['final_pool_state']['total_tao_injected']:.2f}",
                '最终资产价值': f"{summary['key_metrics']['final_asset_value']:.2f}",
                '交易次数': summary['key_metrics']['transaction_count']
            })
        
        comparison_df = pd.DataFrame(comparison_data)
        st.dataframe(comparison_df, use_container_width=True)
        
        # 绘制详细对比图表
        col1, col2 = st.columns(2)
        
        with col1:
            # ROI vs TAO产生速率
            tao_rates = [result['tao_rate'] for result in results.values()]
            rois = [result['summary']['key_metrics']['total_roi'] for result in results.values()]
            descriptions = [result['description'] for result in results.values()]
            
            fig_roi = go.Figure()
            fig_roi.add_trace(go.Scatter(
                x=tao_rates,
                y=rois,
                mode='lines+markers',
                name='ROI',
                text=descriptions,
                line=dict(width=3),
                marker=dict(size=10, color=tao_rates, colorscale='Viridis', showscale=True)
            ))
            fig_roi.update_layout(
                title="TAO产生速率 vs ROI",
                xaxis_title="TAO产生速率 (TAO/区块)",
                yaxis_title="ROI (%)",
                template='plotly_white'
            )
            st.plotly_chart(fig_roi, use_container_width=True)
        
        with col2:
            # TAO注入量对比
            tao_injected = [float(result['summary']['final_pool_state']['total_tao_injected']) for result in results.values()]
            
            fig_injection = go.Figure()
            fig_injection.add_trace(go.Bar(
                x=tao_rates,
                y=tao_injected,
                name='TAO注入量',
                text=[f'{inj:.1f}' for inj in tao_injected],
                textposition='auto',
                marker_color=tao_rates,
                marker_colorscale='Blues'
            ))
            fig_injection.update_layout(
                title="TAO产生速率 vs TAO注入量",
                xaxis_title="TAO产生速率 (TAO/区块)",
                yaxis_title="TAO注入总量",
                template='plotly_white'
            )
            st.plotly_chart(fig_injection, use_container_width=True)
        
        # 价格影响分析
        st.subheader("💡 价格影响分析")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 最终价格对比
            final_prices = [float(result['summary']['final_pool_state']['final_price']) for result in results.values()]
            
            fig_price = go.Figure()
            fig_price.add_trace(go.Scatter(
                x=tao_rates,
                y=final_prices,
                mode='lines+markers',
                name='最终价格',
                line=dict(width=3, color='red'),
                marker=dict(size=8)
            ))
            fig_price.update_layout(
                title="TAO产生速率 vs 最终dTAO价格",
                xaxis_title="TAO产生速率 (TAO/区块)",
                yaxis_title="最终价格 (TAO)",
                template='plotly_white'
            )
            st.plotly_chart(fig_price, use_container_width=True)
        
        with col2:
            # 流动性影响（TAO储备变化）
            # 这里可以添加更多分析图表
            st.info("""
            **🔍 关键发现**
            
            • **高TAO产生速率**：更多流动性，但可能稀释价值
            • **低TAO产生速率**：较少注入，但价格更稳定
            • **平衡点**：根据您的投资策略选择合适的速率
            
            **💡 建议**
            - 短期投资：考虑高产生速率
            - 长期持有：考虑低产生速率
            - 风险偏好：激进选高速率，保守选低速率
            """)
        
        # 最佳策略推荐
        best_roi_idx = rois.index(max(rois))
        best_rate = tao_rates[best_roi_idx]
        best_roi = rois[best_roi_idx]
        best_desc = descriptions[best_roi_idx]
        
        st.success(f"""
        🏆 **最佳ROI表现**: {best_desc}
        - TAO产生速率: {best_rate} TAO/区块
        - ROI: {best_roi:.2f}%
        - 日产生量: {best_rate * 7200:,.0f} TAO
        """)
    
    def run_multiplier_comparison(self, days, budget, threshold):
        """运行触发倍数对比"""
        multipliers = [1.5, 2.0, 2.5, 3.0]
        comparison_results = {}
        
        progress_container = st.container()
        
        for i, multiplier in enumerate(multipliers):
            with progress_container:
                st.info(f"正在测试 {multiplier}x 触发倍数... ({i+1}/{len(multipliers)})")
            
            # 创建配置
            config = {
                "simulation": {
                    "days": days,
                    "blocks_per_day": 7200,
                    "tempo_blocks": 360
                },
                "subnet": {
                    "initial_dtao": "1",
                    "initial_tao": "1",
                    "immunity_blocks": 7200,
                    "moving_alpha": "0.1",
                    "halving_time": 201600
                },
                "market": {
                    "other_subnets_avg_price": "2.0"
                },
                "strategy": {
                    "total_budget_tao": str(budget),
                    "registration_cost_tao": "300",
                    "buy_threshold_price": str(threshold),
                    "buy_step_size_tao": "0.5",
                    "sell_multiplier": "2.0",
                    "sell_trigger_multiplier": str(multiplier),
                    "reserve_dtao": "5000",
                    "sell_delay_blocks": 2
                }
            }
            
            # 运行模拟（不显示进度条）
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    config_path = os.path.join(temp_dir, "config.json")
                    with open(config_path, 'w') as f:
                        json.dump(config, f)
                    
                    simulator = BittensorSubnetSimulator(config_path, temp_dir)
                    summary = simulator.run_simulation()
                    
                    scenario_name = f"触发倍数{multiplier}x"
                    comparison_results[scenario_name] = {
                        'config': config,
                        'summary': summary,
                        'block_data': pd.DataFrame(simulator.block_data),
                        'scenario_name': scenario_name
                    }
                    
            except Exception as e:
                st.error(f"测试 {multiplier}x 失败: {e}")
        
        progress_container.empty()
        
        if comparison_results:
            # 显示对比结果
            self.display_multiplier_comparison(comparison_results)
    
    def display_multiplier_comparison(self, results):
        """显示触发倍数对比结果"""
        st.success("🎉 触发倍数对比完成！")
        
        # 创建对比表格
        comparison_data = []
        for scenario_name, result in results.items():
            summary = result['summary']
            comparison_data.append({
                '触发倍数': scenario_name,
                '策略类型': self.get_strategy_type(float(scenario_name.replace('触发倍数', '').replace('x', ''))),
                'ROI (%)': f"{summary['key_metrics']['total_roi']:.2f}",
                '最终价格 (TAO)': f"{summary['final_pool_state']['final_price']:.4f}",
                '交易次数': summary['key_metrics']['transaction_count'],
                'TAO注入': f"{summary['final_pool_state']['total_tao_injected']:.2f}",
                '最终资产': f"{summary['key_metrics']['final_asset_value']:.2f}"
            })
        
        comparison_df = pd.DataFrame(comparison_data)
        st.dataframe(comparison_df, use_container_width=True)
        
        # 绘制对比图表
        col1, col2 = st.columns(2)
        
        with col1:
            # ROI对比
            multipliers = [float(name.replace('触发倍数', '').replace('x', '')) for name in results.keys()]
            rois = [result['summary']['key_metrics']['total_roi'] for result in results.values()]
            
            fig_roi = go.Figure()
            fig_roi.add_trace(go.Bar(
                x=multipliers,
                y=rois,
                name='ROI',
                text=[f'{r:.1f}%' for r in rois],
                textposition='auto',
                marker_color=['red' if x <= 1.5 else 'blue' if x <= 2.5 else 'green' for x in multipliers]
            ))
            fig_roi.update_layout(
                title="不同触发倍数的ROI对比",
                xaxis_title="触发倍数",
                yaxis_title="ROI (%)",
                template='plotly_white'
            )
            st.plotly_chart(fig_roi, use_container_width=True)
        
        with col2:
            # 最终价格对比
            final_prices = [float(result['summary']['final_pool_state']['final_price']) for result in results.values()]
            
            fig_price = go.Figure()
            fig_price.add_trace(go.Scatter(
                x=multipliers,
                y=final_prices,
                mode='lines+markers',
                name='最终价格',
                line=dict(width=3),
                marker=dict(size=8)
            ))
            fig_price.update_layout(
                title="不同触发倍数的最终价格",
                xaxis_title="触发倍数",
                yaxis_title="最终价格 (TAO)",
                template='plotly_white'
            )
            st.plotly_chart(fig_price, use_container_width=True)
        
        # 最佳策略推荐
        best_roi_idx = rois.index(max(rois))
        best_multiplier = multipliers[best_roi_idx]
        best_roi = rois[best_roi_idx]
        
        st.success(f"""
        🏆 **最佳表现**: {best_multiplier}x 触发倍数
        - ROI: {best_roi:.2f}%
        - 策略类型: {self.get_strategy_type(best_multiplier)}
        """)
    
    def get_strategy_type(self, multiplier):
        """获取策略类型"""
        if multiplier <= 1.5:
            return "激进"
        elif multiplier <= 2.5:
            return "平衡"
        else:
            return "保守"
    
    def render_scenario_comparison(self, selected_scenarios):
        """渲染场景对比"""
        # 准备对比数据
        comparison_metrics = []
        
        for scenario in selected_scenarios:
            result = st.session_state.simulation_results[scenario]
            summary = result['summary']
            
            comparison_metrics.append({
                '场景': scenario,
                'ROI(%)': summary['key_metrics']['total_roi'],
                '最终价格': float(summary['final_pool_state']['final_price']),
                '交易次数': summary['key_metrics']['transaction_count'],
                'TAO注入': float(summary['final_pool_state']['total_tao_injected']),
                '最终资产': summary['key_metrics']['final_asset_value']
            })
        
        # 显示对比表格
        comparison_df = pd.DataFrame(comparison_metrics)
        st.dataframe(comparison_df, use_container_width=True)
        
        # 对比图表
        metric_options = ['ROI(%)', '最终价格', '交易次数', 'TAO注入', '最终资产']
        selected_metric = st.selectbox("选择对比指标", metric_options)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=comparison_df['场景'],
            y=comparison_df[selected_metric],
            name=selected_metric,
            text=pd.to_numeric(comparison_df[selected_metric]).round(2),
            textposition='auto'
        ))
        
        fig.update_layout(
            title=f"{selected_metric} 场景对比",
            xaxis_title="场景",
            yaxis_title=selected_metric,
            template='plotly_white'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def run_threshold_comparison(self, days, budget, multiplier):
        """运行买入阈值对比"""
        thresholds = [0.2, 0.3, 0.4, 0.5]
        comparison_results = {}
        
        progress_container = st.container()
        
        for i, threshold in enumerate(thresholds):
            with progress_container:
                st.info(f"正在测试 {threshold} 买入阈值... ({i+1}/{len(thresholds)})")
            
            # 创建配置
            config = {
                "simulation": {
                    "days": days,
                    "blocks_per_day": 7200,
                    "tempo_blocks": 360,
                    "tao_per_block": "1.0"
                },
                "subnet": {
                    "initial_dtao": "1",
                    "initial_tao": "1",
                    "immunity_blocks": 7200,
                    "moving_alpha": "0.1",
                    "halving_time": 201600
                },
                "market": {
                    "other_subnets_avg_price": "2.0"
                },
                "strategy": {
                    "total_budget_tao": str(budget),
                    "registration_cost_tao": "300",
                    "buy_threshold_price": str(threshold),
                    "buy_step_size_tao": "0.5",
                    "sell_multiplier": "2.0",
                    "sell_trigger_multiplier": str(multiplier),
                    "reserve_dtao": "5000",
                    "sell_delay_blocks": 2
                }
            }
            
            # 运行模拟
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    config_path = os.path.join(temp_dir, "config.json")
                    with open(config_path, 'w') as f:
                        json.dump(config, f)
                    
                    simulator = BittensorSubnetSimulator(config_path, temp_dir)
                    summary = simulator.run_simulation()
                    
                    scenario_name = f"阈值{threshold}"
                    comparison_results[scenario_name] = {
                        'config': config,
                        'summary': summary,
                        'block_data': pd.DataFrame(simulator.block_data),
                        'scenario_name': scenario_name
                    }
                    
            except Exception as e:
                st.error(f"测试阈值 {threshold} 失败: {e}")
        
        progress_container.empty()
        
        if comparison_results:
            # 显示对比结果（类似于触发倍数对比）
            self.display_threshold_comparison(comparison_results)
    
    def display_threshold_comparison(self, results):
        """显示买入阈值对比结果"""
        st.success("🎉 买入阈值对比完成！")
        
        # 创建对比表格
        comparison_data = []
        for scenario_name, result in results.items():
            summary = result['summary']
            threshold = float(scenario_name.replace('阈值', ''))
            
            comparison_data.append({
                '买入阈值': f"{threshold:.1f}",
                '策略特点': self.get_threshold_strategy_type(threshold),
                'ROI (%)': f"{summary['key_metrics']['total_roi']:.2f}",
                '最终价格': f"{summary['final_pool_state']['final_price']:.4f}",
                '交易次数': summary['key_metrics']['transaction_count'],
                '最终资产': f"{summary['key_metrics']['final_asset_value']:.2f}"
            })
        
        comparison_df = pd.DataFrame(comparison_data)
        st.dataframe(comparison_df, use_container_width=True)
        
        # 阈值对比图表
        thresholds = [float(name.replace('阈值', '')) for name in results.keys()]
        rois = [result['summary']['key_metrics']['total_roi'] for result in results.values()]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=thresholds,
            y=rois,
            mode='lines+markers',
            name='ROI',
            line=dict(width=3),
            marker=dict(size=10)
        ))
        fig.update_layout(
            title="买入阈值 vs ROI",
            xaxis_title="买入阈值",
            yaxis_title="ROI (%)",
            template='plotly_white'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    def get_threshold_strategy_type(self, threshold):
        """获取阈值策略类型"""
        if threshold <= 0.25:
            return "非常激进"
        elif threshold <= 0.35:
            return "激进"
        elif threshold <= 0.45:
            return "平衡"
        else:
            return "保守"

def main():
    """主函数"""
    interface = FullWebInterface()
    
    # 渲染头部
    interface.render_header()
    
    # 主要内容区域
    tab1, tab2, tab3 = st.tabs(["🎯 单场景模拟", "🔄 多策略对比", "📊 结果管理"])
    
    with tab1:
        # 配置面板（包含运行按钮）
        config_and_button = interface.render_sidebar_config()
        config_from_ui = config_and_button['config']
        run_button = config_and_button['run_button']
        
        # 场景名称输入
        scenario_name = st.text_input("场景名称", value=f"场景-{datetime.now().strftime('%H%M%S')}")
        
        if run_button:
            if scenario_name in st.session_state.simulation_results:
                st.warning(f"场景 '{scenario_name}' 已存在，将覆盖原结果")
            
            with st.spinner("正在运行模拟..."):
                # 关键修正：将从UI获取的配置传递给运行函数
                result = interface.run_simulation(config_from_ui, scenario_name)
                
                if result:
                    st.session_state.simulation_results[scenario_name] = result
                    interface.render_simulation_results(result)
    
    with tab2:
        interface.render_comparison_tools()
    
    with tab3:
        st.header("📊 结果管理")
        
        if st.session_state.simulation_results:
            st.subheader("已保存的模拟结果")
            
            for scenario_name, result in st.session_state.simulation_results.items():
                with st.expander(f"📋 {scenario_name}"):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("ROI", f"{result['summary']['key_metrics']['total_roi']:.2f}%")
                    with col2:
                        st.metric("最终价格", f"{result['summary']['final_pool_state']['final_price']:.4f} TAO")
                    with col3:
                        if st.button(f"删除 {scenario_name}", key=f"delete_{scenario_name}"):
                            del st.session_state.simulation_results[scenario_name]
                            st.rerun()
        else:
            st.info("暂无保存的模拟结果")

if __name__ == "__main__":
    main() 