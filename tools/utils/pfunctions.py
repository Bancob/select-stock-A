"""
未经授权，不得复制、修改、或使用本代码的全部或部分内容。仅限个人学习用途，禁止商业用途。
"""
import os
import platform
import webbrowser
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional

import numpy as np
import pandas as pd
from plotly import subplots
import plotly.express as px
import plotly.graph_objs as go
from plotly.offline import plot
from plotly.subplots import make_subplots
from tools.utils.tfunctions import float_num_process


# 绘制IC图
def draw_ic_plotly(x, y1, y2, title='', info='', pic_size=(1800, 600), save_path=None):
    """
    IC画图函数
    :param save_path: 保存的存储路径
    :param x: x轴，时间轴
    :param y1: 第一个y轴，每周期的IC
    :param y2: 第二个y轴，累计的IC
    :param title: 图标题
    :param info: IC字符串
    :param pic_size: 图片大小
    :return: None
    """

    # 创建子图
    fig = make_subplots(rows=1, cols=1, specs=[[{"secondary_y": True}]])

    # 添加柱状图轨迹
    fig.add_trace(
        go.Bar(
            x=x,  # X轴数据
            y=y1,  # 第一个y轴数据
            name=y1.name,  # 第一个y轴的名字
            marker={
                'color': 'orange',  # 设置颜色
                'line_color': 'orange'  # 设置柱状图边框的颜色
            }
        ),
        row=1, col=1, secondary_y=False
    )

    # 添加折线图轨迹
    fig.add_trace(
        go.Scatter(
            x=x,  # X轴数据
            y=y2,  # 第二个y轴数据
            text=y2,  # 第二个y轴的文本
            name=y2.name,  # 第二个y轴的名字
            marker={'color': 'blue'}  # 设置颜色
        ),
        row=1, col=1, secondary_y=True
    )

    # 更新布局
    fig.update_layout(
        plot_bgcolor='rgb(255, 255, 255)',  # 设置绘图区背景色
        width=pic_size[0],  # 调整宽度
        height=pic_size[1],  # 调整高度
        title={
            'text': title,  # 标题文本
            'x': 0.377,  # 标题相对于绘图区的水平位置
            'y': 0.9,  # 标题相对于绘图区的垂直位置
            'xanchor': 'center',  # 标题的水平对齐方式
            'font': {'color': 'green', 'size': 20}  # 标题的颜色和大小
        },
        xaxis=dict(domain=[0.0, 0.73]),  # 设置 X 轴的显示范围
        legend=dict(
            x=0.8,  # 图例相对于绘图区的水平位置
            y=1.0,  # 图例相对于绘图区的垂直位置
            bgcolor='white',  # 图例背景色
            bordercolor='gray',  # 图例边框颜色
            borderwidth=1  # 图例边框宽度
        ),
        annotations=[
            dict(
                x=x.iloc[len(x) // 2],  # 文字的 x 轴位置
                y=0.6,  # 文字的 y 轴位置
                text=info,  # 文字内容
                showarrow=False,  # 是否显示箭头
                font=dict(
                    size=14  # 设置文字的字体大小
                )
            )
        ],
        hovermode="x unified",
        hoverlabel=dict(bgcolor='rgba(255,255,255,0.5)', )
    )

    # 是否要保存图像
    if save_path:
        plot(figure_or_data=fig, filename=str(save_path), auto_open=False)

    # 显示图像
    fig.show()


# 绘制柱状图
def draw_bar_plotly(x, y, title='', pic_size=(1800, 600), y_range=(), save_path=None):
    """
    柱状图画图函数
    :param x: 放到X轴上的数据
    :param y: 放到Y轴上的数据
    :param title: 图标题
    :param pic_size: 图大小
    :param y_range: Y轴范围
    :param save_path: 保存路径
    :return: 返回柱状图
    """

    # 创建子图
    fig = make_subplots()

    y_ = y.map(float_num_process, na_action='ignore')

    # 添加柱状图轨迹
    fig.add_trace(go.Bar(
        x=x,  # X轴数据
        y=y,  # Y轴数据
        text=y_,  # Y轴文本
        name=x.name  # 图里名字
    ), row=1, col=1)

    # 更新X轴的tick
    fig.update_xaxes(
        tickmode='array',
        tickvals=x
    )
    # 设置Y轴范围
    if y_range:
        fig.update_yaxes(range=[y_range[0], y_range[1]])
    # 更新布局
    fig.update_layout(
        plot_bgcolor='rgb(255, 255, 255)',  # 设置绘图区背景色
        width=pic_size[0],  # 宽度
        height=pic_size[1],  # 高度
        title={
            'text': title,  # 标题文本
            'x': 0.377,  # 标题相对于绘图区的水平位置
            'y': 0.9,  # 标题相对于绘图区的垂直位置
            'xanchor': 'center',  # 标题的水平对齐方式
            'font': {'color': 'green', 'size': 20}  # 标题的颜色和大小
        },
        xaxis=dict(domain=[0.0, 0.73]),  # 设置 X 轴的显示范围
        showlegend=True,  # 是否显示图例
        legend=dict(
            x=0.8,  # 图例相对于绘图区的水平位置
            y=1.0,  # 图例相对于绘图区的垂直位置
            bgcolor='white',  # 图例背景色
            bordercolor='gray',  # 图例边框颜色
            borderwidth=1  # 图例边框宽度
        )
    )

    if save_path:
        plot(figure_or_data=fig, filename=str(save_path), auto_open=False)
    # 将图表转换为 HTML 格式
    return_fig = plot(fig, include_plotlyjs=True, output_type='div')

    return return_fig


def draw_hedge_signal_plotly(df, save_path, title, trade_df, _res_loc, buy_method='开盘', pic_size=(1880, 1000)):
    time_data = df['交易日期']
    # 构建画布左轴
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True)
    # 创建自定义悬停文本
    hover_text = []
    for date, pct_change, open_change in zip(time_data.dt.date.astype(str),
                                             df['涨跌幅'].apply(lambda x: str(round(100 * x, 2)) + '%'),
                                             df[f'{buy_method.replace("价", "")}买入涨跌幅'].apply(
                                                 lambda x: str(round(100 * x, 2)) + '%')):
        hover_text.append(
            f'日期: {date}<br>涨跌幅: {pct_change}<br>{buy_method}买入涨跌幅: {open_change}')

    # 绘制k线图
    fig.add_trace(go.Candlestick(
        x=time_data,
        open=df['开盘价_复权'],  # 字段数据必须是元组、列表、numpy数组、或者pandas的Series数据
        high=df['最高价_复权'],
        low=df['最低价_复权'],
        close=df['收盘价_复权'],
        name='k线',
        increasing=dict(line=dict(color='red')),  # 设置上涨蜡烛的颜色
        decreasing=dict(line=dict(color='green')),  # 设置下跌蜡烛的颜色
        # text=time_data.dt.date.astype(str)  # 自定义悬停文本把日期加上
        text=hover_text,
    ), row=1, col=1)

    # 更新x轴设置，非交易日在X轴上排除
    date_range = pd.date_range(start=time_data.min(), end=time_data.max(), freq='D')
    miss_dates = date_range[~date_range.isin(time_data)].to_list()
    fig.update_xaxes(rangebreaks=[dict(values=miss_dates)])

    # 标记买卖点的数据，绘制在最后
    mark_point_list = []
    for i in df[(df['买入时间'].notna()) | (df['卖出时间'].notna())].index:
        # 获取买卖点信息
        open_signal = df.loc[i, '买入时间']
        close_signal = df.loc[i, '卖出时间']
        # 只有开仓信号，没有平仓信号
        if pd.notnull(open_signal) and pd.isnull(close_signal):
            signal = open_signal
            # 标记买卖点，在最低价下方标记
            y = df.at[i, '最低价_复权'] * 0.99
        # 没有开仓信号，只有平仓信号
        elif pd.isnull(open_signal) and pd.notnull(close_signal):
            signal = close_signal
            # 标记买卖点，在最高价上方标记
            y = df.at[i, '最高价_复权'] * 1.01
        else:  # 同时有开仓信号和平仓信号
            signal = f'{open_signal}_{close_signal}'
            # 标记买卖点，在最高价上方标记
            y = df.at[i, '最高价_复权'] * 1.01
        mark_point_list.append({
            'x': df.at[i, '交易日期'],
            'y': y,
            'showarrow': True,
            'text': signal,
            'ax': 0,
            'ay': 50 * {'卖出': -1, '买入': 1, '买入_卖出': 1}[signal],
            'arrowhead': 1 + {'卖出': 0, '买入': 2, '买入_卖出': 2}[signal],
        })

    # 绘制成交额
    fig.add_trace(go.Bar(x=time_data, y=df['成交额'], name='成交额'), row=2, col=1)

    # 做两个信息表
    res_loc = _res_loc.copy()
    res_loc[['累计持股收益', '次均收益率_复利', '次均收益率_单利', '日均收益率_复利', '日均收益率_单利']] = res_loc[
        ['累计持股收益', '次均收益率_复利', '次均收益率_单利', '日均收益率_复利', '日均收益率_单利']].apply(
        lambda x: str(round(100 * x, 3)) + '%' if isinstance(x, float) else x)
    table_trace = go.Table(header=dict(
        values=[[title.split('_')[1]], [title.split('_')[0]]]),
        cells=dict(
            values=[res_loc.index.to_list()[2:-1], res_loc.to_list()[2:-1]]),
        domain=dict(x=[0.8, 0.95], y=[0.5, 0.9]),
    )
    fig.add_trace(table_trace)

    table_trace = go.Table(header=dict(values=list(['买入日期', '卖出日期', '买入价', '卖出价', '收益率'])),
                           cells=dict(
                               values=[trade_df['买入日期'].dt.date, trade_df['卖出日期'].dt.date, trade_df['买入价'],
                                       trade_df['卖出价'], trade_df['收益率']]),
                           domain=dict(x=[0.75, 1.0], y=[0.1, 0.5]))
    fig.add_trace(table_trace)

    # 更新画布布局，把买卖点标记上
    fig.update_layout(annotations=mark_point_list, template="none", width=pic_size[0], height=pic_size[1],
                      title_text=title, hovermode='x',
                      yaxis=dict(domain=[0.25, 1.0]), xaxis=dict(domain=[0.0, 0.73]),
                      yaxis2=dict(domain=[0.05, 0.25]), xaxis2=dict(domain=[0.0, 0.73]),
                      xaxis_rangeslider_visible=False,
                      )
    fig.update_layout(
        legend=dict(x=0.75, y=1)
    )
    # 保存路径
    save_path = save_path / f'{title}.html'
    plot(figure_or_data=fig, filename=str(save_path), auto_open=False)


def draw_params_heatmap_plotly(df, title=''):
    """
    生成热力图
    """
    draw_df = df.copy()

    draw_df.replace(np.nan, '', inplace=True)
    # 修改temp的index和columns为str
    draw_df.index = draw_df.index.astype(str)
    draw_df.columns = draw_df.columns.astype(str)

    fig = px.imshow(
        draw_df,
        title=title,
        text_auto=True,
        color_continuous_scale='Viridis',
        # aspect='auto'
    )

    # 关键修改：启用响应式布局
    fig.update_layout(
        paper_bgcolor='rgba(255,255,255,1)',
        plot_bgcolor='rgba(255,255,255,1)',
        autosize=True,
        margin=dict(l=20, r=20, t=40, b=20),  # 减少边距

        title={
            'text': f'{title}',
            'y': 0.95,
            'x': 0.5,
            'font': {'color': 'green', 'size': 16}  # 标题字号适当减小
        }
    )

    return plot(
        fig,
        include_plotlyjs=True,
        output_type='div',
        config={
            'responsive': True,  # 启用响应式配置
            'displayModeBar': True  # 显示工具栏
        }
    )


def draw_params_bar_plotly(df: pd.DataFrame, title: str):
    draw_df = df.copy()
    rows = len(draw_df.columns)
    s = (1 / (rows - 1)) * 0.5
    fig = subplots.make_subplots(rows=rows, cols=1, shared_xaxes=True, shared_yaxes=True, vertical_spacing=s)

    for i, col_name in enumerate(draw_df.columns):
        trace = go.Bar(x=draw_df.index, y=draw_df[col_name], name=f"{col_name}")
        fig.add_trace(trace, i + 1, 1)
        # 更新每个子图的x轴属性
        fig.update_xaxes(showticklabels=True, row=i + 1, col=1)  # 旋转x轴标签以避免重叠

    # 更新每个子图的y轴标题
    for i, col_name in enumerate(draw_df.columns):
        fig.update_xaxes(title_text=col_name, row=i + 1, col=1)

    fig.update_layout(height=200 * rows, showlegend=True, title={
        'text': f'{title}',  # 标题文本
        'x': 0.5,
        'yanchor': 'top',
        'font': {'color': 'green', 'size': 20}  # 标题的颜色和大小
    }, )

    return_fig = plot(fig, include_plotlyjs=True, output_type='div')
    return return_fig


def merge_html_flexible(
        fig_list: List[str],
        html_path: Path,
        title: Optional[str] = None,
        link_url: Optional[str] = None,
        link_text: Optional[str] = None,
        show: bool = True,
):
    """
    将多个Plotly图表合并到一个HTML文件，并允许灵活配置标题、副标题和链接

    :param fig_list: 包含Plotly图表HTML代码的列表
    :param html_path: 输出的HTML文件路径
    :param title: 主标题内容（例如"因子分析报告"）
    :param link_url: 右侧链接的URL地址
    :param link_text: 右侧链接的显示文本
    :param show: 是否自动打开HTML文件
    :return: 生成的HTML文件路径
    :raises OSError: 文件操作失败时抛出
    """

    # 构建header部分
    header_html = []
    if title:
        header_html.append(
            f'<div class="report-title">{title}</div>'
        )

    if link_url and link_text:
        header_html.append(
            f'<a href="{link_url}" class="report-link" target="_blank">{link_text} →</a>'
        )

    # 组合header部分
    header_str = ""
    if header_html:
        header_str = f'<div class="header">{"".join(header_html)}</div>'

    # 构建完整HTML内容
    html_template = f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>

            .header {{
                display: flex;
                justify-content: space-between;  /* 自动分配两端对齐 */
                align-items: center;
                padding: 20px 40px;  /* 横向增加内边距 */
            }}

            .figure-container {{
                width: 90%;
                margin: 20px auto;
            }}

            .report-title {{
                font-size: 20px;
                color: #2c3e50;
                margin-right: 200px
            }}

            .report-link {{
                font-size: 20px;
                text-decoration: none;
                color: #3498db;
                font-weight: 500;
                 margin-right: 300px;  /* 可选：添加右侧边距 */
            }}

            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 0;
            }}
        </style>
    </head>
    <body>
        {header_str}
        <div class="charts-wrapper">
            {"".join(f'<div class="figure-container">{fig}</div>' for fig in fig_list)}
        </div>
    </body>
    </html>
    """

    # 自动打开HTML文件
    if show:
        # 定义局部的 write_html 函数，并包装为具有 write_html 属性的对象
        def write_html(file_path: Path):
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_template)

        wrapped_html = SimpleNamespace(write_html=write_html)
        show_without_plot_native_show(wrapped_html, html_path)


def show_without_plot_native_show(fig, save_path: str | Path):
    save_path = save_path.absolute()
    print('⚠️ 因为新版pycharm默认开启sci-view功能，导致部分同学会在.show()的时候假死')
    print(f'因此我们会先保存HTML到: {save_path}, 然后调用默认浏览器打开')
    fig.write_html(save_path)

    """
    跨平台在默认浏览器中打开 URL 或文件
    """
    system_name = platform.system()  # 检测操作系统
    if system_name == "Darwin":  # macOS
        os.system(f'open "" "{save_path}"')
    elif system_name == "Windows":  # Windows
        os.system(f'start "" "{save_path}"')
    elif system_name == "Linux":  # Linux
        os.system(f'xdg-open "" "{save_path}"')
    else:
        # 如果不确定操作系统，尝试使用 webbrowser 模块
        webbrowser.open(str(save_path))
