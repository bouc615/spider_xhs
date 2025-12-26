#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书爬虫Web API
提供JSON数据输出和HTML可视化交互
"""

import json
import os
import time
import uuid
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from threading import Thread
from main import Data_Spider
from xhs_utils.common_util import init
from loguru import logger

app = Flask(__name__)
CORS(app)


class WebSpider:
    def __init__(self):
        self.cookies_str, self.base_path = init()
        self.data_spider = Data_Spider()
        self.tasks = {}  # 存储任务状态
        self.results_dir = "web_data"
        os.makedirs(self.results_dir, exist_ok=True)

    def extract_note_data(self, note_url, cookies_str=None):
        """
        提取单个笔记的完整数据
        :param note_url: 笔记URL
        :param cookies_str: Cookie字符串，如果为None则使用初始化时的Cookie
        """
        # 优先使用传入的cookie，否则使用默认的
        cookies_to_use = cookies_str or self.cookies_str
        try:
            # 获取笔记基本信息
            success, msg, note_info = self.data_spider.spider_note(
                note_url, cookies_to_use
            )
            if not success:
                logger.error(f"获取笔记信息失败: {msg}")
                return None

            # 获取评论 - 使用简化方法
            logger.info(f"开始获取笔记评论: {note_url}")
            comments = []
            try:
                # 解析note_id和xsec_token
                import urllib.parse

                urlParse = urllib.parse.urlparse(note_url)
                note_id = urlParse.path.split("/")[-1]

                xsec_token = ""
                if urlParse.query:
                    kvs = urlParse.query.split("&")
                    for kv in kvs:
                        if "=" in kv and kv.startswith("xsec_token="):
                            xsec_token = kv.split("=", 1)[1]
                            break

                logger.info(
                    f"解析得到 note_id: {note_id}, xsec_token: {xsec_token[:20]}..."
                )

                # 获取第一页评论进行测试
                success, msg, res_json = self.data_spider.xhs_apis.get_note_out_comment(
                    note_id, "", xsec_token, cookies_to_use
                )

                if (
                    success
                    and res_json
                    and "data" in res_json
                    and "comments" in res_json["data"]
                ):
                    comments = res_json["data"]["comments"]
                    logger.info(f"成功获取评论数量: {len(comments)}")
                else:
                    logger.warning(f"获取评论失败: {msg}")

            except Exception as e:
                logger.error(f"获取评论异常: {e}")
                comments = []

            # 提取图片链接
            pictures = []
            if "image_list" in note_info:
                for img in note_info["image_list"]:
                    img_url = None
                    if isinstance(img, dict) and "url" in img:
                        img_url = img["url"]
                    elif isinstance(img, str):
                        img_url = img

                    if img_url:
                        pictures.append(img_url)
                        logger.info(f"提取到图片URL: {img_url}")

            # 提取评论内容
            comment_texts = []
            logger.info(f"处理评论数量: {len(comments)}")

            for comment in comments:
                if isinstance(comment, dict):
                    # 提取主评论内容
                    content = comment.get("content", "")
                    if content:
                        # 清理评论内容，移除表情符号标记
                        clean_content = content.replace("[大笑R]", "😄").replace(
                            "[偷笑R]", "😏"
                        )
                        comment_texts.append(clean_content)
                        logger.info(f"提取评论: {clean_content[:50]}...")

                    # 提取子评论
                    sub_comments = comment.get("sub_comments", [])
                    for sub_comment in sub_comments:
                        if isinstance(sub_comment, dict):
                            sub_content = sub_comment.get("content", "")
                            if sub_content:
                                clean_sub_content = sub_content.replace(
                                    "[大笑R]", "😄"
                                ).replace("[偷笑R]", "😏")
                                comment_texts.append(
                                    f"↳ {clean_sub_content}"
                                )  # 添加缩进标识子评论
                                logger.info(f"提取子评论: {clean_sub_content[:50]}...")
                elif isinstance(comment, str):
                    comment_texts.append(comment)

            logger.info(f"提取到评论文本数量: {len(comment_texts)}")

            return {
                "link": note_url,
                "title": note_info.get("title", ""),
                "content": note_info.get("desc", ""),
                "pictures": pictures,
                "comments": comment_texts,
            }

        except Exception as e:
            logger.error(f"提取笔记数据失败: {e}")
            return None

    def search_and_collect(self, keyword, num_notes, task_id, cookie=None):
        """
        搜索并收集数据的后台任务
        """
        try:
            logger.info(f"开始搜索任务 {task_id}: {keyword}")
            self.tasks[task_id]["status"] = "running"
            self.tasks[task_id]["progress"] = 0

            # 使用传入的Cookie或默认Cookie
            cookies_str = cookie or self.cookies_str

            # 搜索笔记
            success, msg, notes = self.data_spider.xhs_apis.search_some_note(
                keyword,
                num_notes,
                cookies_str,
                sort_type_choice=2,  # 按最多点赞排序
                note_type=0,  # 不限类型
                proxies=None,
            )

            if not success:
                self.tasks[task_id]["status"] = "failed"
                self.tasks[task_id]["error"] = msg
                return

            # 过滤笔记类型
            notes = list(filter(lambda x: x["model_type"] == "note", notes))
            logger.info(f"找到 {len(notes)} 条相关笔记")

            collected_data = []
            total_notes = min(len(notes), num_notes)

            for i, note in enumerate(notes[:num_notes]):
                try:
                    note_url = f"https://www.xiaohongshu.com/explore/{note['id']}?xsec_token={note['xsec_token']}"

                    logger.info(f"处理第 {i+1}/{total_notes} 个笔记...")
                    note_data = self.extract_note_data(note_url, cookies_str)

                    if note_data:
                        collected_data.append(note_data)

                    # 更新进度
                    progress = int((i + 1) / total_notes * 100)
                    self.tasks[task_id]["progress"] = progress

                    # 添加延时避免请求过快
                    time.sleep(1)

                except Exception as e:
                    logger.error(f"处理第 {i+1} 个笔记时出错: {e}")
                    continue

            # 保存结果
            result_data = {
                "task": keyword,
                "data": collected_data,
                "id": task_id,
                "created_at": datetime.now().isoformat(),
                "total_notes": len(collected_data),
            }

            result_file = os.path.join(self.results_dir, f"{task_id}.json")
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)

            self.tasks[task_id]["status"] = "completed"
            self.tasks[task_id]["progress"] = 100
            self.tasks[task_id]["result_file"] = result_file

            logger.info(f"任务 {task_id} 完成，收集了 {len(collected_data)} 条数据")

        except Exception as e:
            logger.error(f"任务 {task_id} 执行失败: {e}")
            self.tasks[task_id]["status"] = "failed"
            self.tasks[task_id]["error"] = str(e)


web_spider = WebSpider()


@app.route("/")
def index():
    """主页"""
    return render_template("index.html")


@app.route("/api/search", methods=["POST"])
def start_search():
    """开始搜索任务"""
    data = request.get_json()
    keyword = data.get("keyword", "").strip()
    num_notes = data.get("num_notes", 10)
    cookie = data.get("cookie", "").strip()

    if not keyword:
        return jsonify({"error": "关键词不能为空"}), 400

    if num_notes <= 0 or num_notes > 100:
        return jsonify({"error": "笔记数量必须在1-100之间"}), 400

    if not cookie:
        return jsonify({"error": "登录凭证不能为空"}), 400

    # 生成任务ID
    task_id = int(time.time() * 1000)  # 使用时间戳作为ID

    # 初始化任务状态
    web_spider.tasks[task_id] = {
        "keyword": keyword,
        "num_notes": num_notes,
        "cookie": cookie,
        "status": "pending",
        "progress": 0,
        "created_at": datetime.now().isoformat(),
    }

    # 启动后台任务
    thread = Thread(
        target=web_spider.search_and_collect, args=(keyword, num_notes, task_id, cookie)
    )
    thread.daemon = True
    thread.start()

    return jsonify(
        {"task_id": task_id, "message": "搜索任务已启动", "status": "pending"}
    )


@app.route("/api/test_cookie", methods=["POST"])
def test_cookie():
    """测试登录凭证有效性"""
    data = request.get_json()
    cookie = data.get("cookie", "").strip()

    if not cookie:
        return jsonify({"success": False, "message": "登录凭证不能为空"}), 400

    # 基本格式验证
    if "=" not in cookie or len(cookie) < 50:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "登录凭证格式不正确，请确保复制完整的身份验证信息",
                }
            ),
            400,
        )

    # 检查是否包含必要的字段
    required_fields = ["a1", "web_session"]
    missing_fields = []
    for field in required_fields:
        if f"{field}=" not in cookie:
            missing_fields.append(field)

    if missing_fields:
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"登录凭证缺少必要字段: {', '.join(missing_fields)}，请确保已登录小红书后复制完整信息",
                }
            ),
            400,
        )

    try:
        # 使用Cookie测试一个简单的API调用
        success, msg, result = web_spider.data_spider.xhs_apis.get_homefeed_all_channel(
            cookie
        )

        if success:
            # 尝试获取用户信息来进一步验证
            try:
                user_success, user_msg, user_info = (
                    web_spider.data_spider.xhs_apis.get_user_self_info(cookie)
                )
                if user_success and user_info and "data" in user_info:
                    user_name = user_info["data"].get("nickname", "未知用户")
                    return jsonify(
                        {
                            "success": True,
                            "message": f"登录凭证有效，当前用户: {user_name}",
                        }
                    )
                else:
                    return jsonify({"success": True, "message": "登录凭证有效"})
            except:
                return jsonify({"success": True, "message": "登录凭证有效"})
        else:
            # 根据错误信息提供更具体的反馈
            if "登录" in msg or "login" in msg.lower():
                return jsonify(
                    {
                        "success": False,
                        "message": "登录凭证已过期，请重新登录小红书后获取新的身份验证信息",
                    }
                )
            elif "权限" in msg or "permission" in msg.lower():
                return jsonify(
                    {
                        "success": False,
                        "message": "登录凭证权限不足，请确保已完全登录小红书",
                    }
                )
            else:
                return jsonify(
                    {"success": False, "message": f"登录凭证验证失败: {msg}"}
                )

    except Exception as e:
        logger.error(f"测试登录凭证失败: {e}")
        error_msg = str(e)
        if "timeout" in error_msg.lower():
            return jsonify(
                {"success": False, "message": "网络超时，请检查网络连接后重试"}
            )
        elif "connection" in error_msg.lower():
            return jsonify(
                {"success": False, "message": "网络连接失败，请检查网络设置"}
            )
        else:
            return jsonify({"success": False, "message": f"测试失败: {error_msg}"})


@app.route("/api/task/<int:task_id>/status")
def get_task_status(task_id):
    """获取任务状态"""
    if task_id not in web_spider.tasks:
        return jsonify({"error": "任务不存在"}), 404

    task = web_spider.tasks[task_id]
    return jsonify(
        {
            "task_id": task_id,
            "status": task["status"],
            "progress": task["progress"],
            "keyword": task["keyword"],
            "num_notes": task["num_notes"],
            "created_at": task["created_at"],
            "error": task.get("error", None),
        }
    )


@app.route("/api/data/<int:task_id>")
def get_data(task_id):
    """获取任务结果数据"""
    result_file = os.path.join(web_spider.results_dir, f"{task_id}.json")

    if not os.path.exists(result_file):
        return jsonify({"error": "数据不存在"}), 404

    try:
        with open(result_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"读取数据失败: {str(e)}"}), 500


@app.route("/api/tasks")
def list_tasks():
    """获取所有任务列表"""
    tasks_list = []
    for task_id, task_info in web_spider.tasks.items():
        tasks_list.append(
            {
                "id": task_id,
                "keyword": task_info["keyword"],
                "status": task_info["status"],
                "progress": task_info["progress"],
                "created_at": task_info["created_at"],
            }
        )

    # 按创建时间倒序排列
    tasks_list.sort(key=lambda x: x["created_at"], reverse=True)
    return jsonify(tasks_list)


@app.route("/view/<int:task_id>")
def view_result(task_id):
    """查看结果页面"""
    return render_template("result.html", task_id=task_id)


@app.route("/test_image")
def test_image():
    """图片代理测试页面"""
    return render_template("test_image.html")


@app.route("/api/export/comments/<int:task_id>")
def export_comments(task_id):
    """导出评论数据"""
    note_index = request.args.get("note_index", type=int)
    export_format = request.args.get("format", "json")  # json, csv, txt

    result_file = os.path.join(web_spider.results_dir, f"{task_id}.json")

    if not os.path.exists(result_file):
        return jsonify({"error": "数据不存在"}), 404

    try:
        with open(result_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 收集评论数据
        comments_data = []

        if note_index is not None:
            # 导出特定笔记的评论
            if 0 <= note_index < len(data["data"]):
                note = data["data"][note_index]
                for comment in note["comments"]:
                    comments_data.append(
                        {
                            "note_title": note["title"],
                            "note_link": note["link"],
                            "comment": comment,
                            "note_index": note_index,
                        }
                    )
        else:
            # 导出所有评论
            for idx, note in enumerate(data["data"]):
                for comment in note["comments"]:
                    comments_data.append(
                        {
                            "note_title": note["title"],
                            "note_link": note["link"],
                            "comment": comment,
                            "note_index": idx,
                        }
                    )

        # 根据格式返回数据
        if export_format == "json":
            response_data = {
                "task": data["task"],
                "export_time": datetime.now().isoformat(),
                "total_comments": len(comments_data),
                "comments": comments_data,
            }

            response = app.response_class(
                json.dumps(response_data, ensure_ascii=False, indent=2),
                mimetype="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename=comments_{task_id}.json",
                    "Content-Type": "application/json; charset=utf-8",
                },
            )
            return response

        elif export_format == "csv":
            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)

            # 写入表头
            writer.writerow(["笔记标题", "笔记链接", "评论内容", "笔记索引"])

            # 写入数据
            for item in comments_data:
                writer.writerow(
                    [
                        item["note_title"],
                        item["note_link"],
                        item["comment"],
                        item["note_index"],
                    ]
                )

            response = app.response_class(
                output.getvalue(),
                mimetype="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=comments_{task_id}.csv",
                    "Content-Type": "text/csv; charset=utf-8",
                },
            )
            return response

        elif export_format == "txt":
            output_lines = []
            output_lines.append(f"评论导出 - {data['task']}")
            output_lines.append(
                f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            output_lines.append(f"评论总数: {len(comments_data)}")
            output_lines.append("=" * 50)
            output_lines.append("")

            current_note = None
            for item in comments_data:
                if current_note != item["note_title"]:
                    current_note = item["note_title"]
                    output_lines.append(f"【{current_note}】")
                    output_lines.append(f"链接: {item['note_link']}")
                    output_lines.append("-" * 30)

                output_lines.append(f"• {item['comment']}")
                output_lines.append("")

            response = app.response_class(
                "\n".join(output_lines),
                mimetype="text/plain",
                headers={
                    "Content-Disposition": f"attachment; filename=comments_{task_id}.txt",
                    "Content-Type": "text/plain; charset=utf-8",
                },
            )
            return response

        else:
            return jsonify({"error": "不支持的导出格式"}), 400

    except Exception as e:
        logger.error(f"导出评论失败: {e}")
        return jsonify({"error": f"导出失败: {str(e)}"}), 500


@app.route("/proxy_image")
def proxy_image():
    """代理图片请求，解决403问题"""
    image_url = request.args.get("url")
    if not image_url:
        logger.error("代理图片请求缺少URL参数")
        return "Missing URL parameter", 400

    try:
        logger.info(f"代理图片请求: {image_url}")

        # 添加小红书的请求头来绕过防盗链
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": "https://www.xiaohongshu.com/",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        # 添加超时设置
        response = requests.get(image_url, headers=headers, timeout=10, stream=True)

        logger.info(f"图片请求响应状态: {response.status_code}")

        if response.status_code == 200:
            # 获取内容类型
            content_type = response.headers.get("content-type", "image/jpeg")

            # 返回图片数据
            return app.response_class(
                response.content,
                mimetype=content_type,
                headers={
                    "Cache-Control": "public, max-age=3600",  # 缓存1小时
                    "Access-Control-Allow-Origin": "*",
                },
            )
        else:
            logger.warning(f"图片请求失败，状态码: {response.status_code}")
            return (
                f"Failed to fetch image: {response.status_code}",
                response.status_code,
            )

    except requests.exceptions.Timeout:
        logger.error(f"图片请求超时: {image_url}")
        return "Request timeout", 408
    except requests.exceptions.RequestException as e:
        logger.error(f"图片请求异常: {e}")
        return f"Request error: {str(e)}", 500
    except Exception as e:
        logger.error(f"代理图片请求失败: {e}")
        return f"Error: {str(e)}", 500


if __name__ == "__main__":
    print("🚀 小红书爬虫Web服务启动...")
    print("📱 访问 http://localhost:8888 开始使用")
    app.run(debug=True, host="0.0.0.0", port=8888)
