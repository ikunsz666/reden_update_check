from mcdreforged.api.all import *

import os
import yaml
from yaml import Loader
import zipfile
import json
import requests
import hashlib


def calculate_hash(file_path):  # sha1验证
    with open(file_path, "rb") as f:
        data = f.read()
        hash_object = hashlib.sha1(data)
        hex_dig = hash_object.hexdigest()
        return hex_dig


def GetModfileList(directory):  # 检索所有模组
    return [
        f for f in os.listdir(directory) if f.lower().endswith(".jar") and "reden" in f.lower()
    ]

def extract_mod_info(filename, mods_path):  # 提取模组信息
    try:
        with zipfile.ZipFile(os.path.join(mods_path, filename), "r") as zip_ref:
            # 直接打开zip文件中的fabric.mod.json文件
            with zip_ref.open("fabric.mod.json", "r") as fabric_modinfo:
                json_file = json.load(fabric_modinfo)
            if json_file.get("id") == "reden":  # 获取id
                return filename  # 返回模组文件名

    except zipfile.BadZipFile:  # 这东西会爆错...
        pass

def find_mod_file(ModList, mods_path):  # 查找模组文件
    modFile_name = "None"
    for filename in ModList:
        modFile_name = extract_mod_info(filename, mods_path)
        if modFile_name is not None:  # 找到
            break
    return modFile_name


def download_and_shutdown(server, modFile_name, mods_path):  # 下载重启
    ApiAddress = "https://api.modrinth.com/v2/project/reden/version"  # reden信息获取
    try:
        res = requests.get(ApiAddress, timeout=5)
        response = json.loads(res.text)
        if (response[0].get("files")[0].get("filename") == modFile_name):  # 模组名称是否和最新版本的名称一致
            server.logger.info(server.tr("reden-update-check.ok"))
        else:
            server.logger.info(server.tr("reden-update-check.new"))
            downloadresp = requests.get(response[0].get("files")[0].get("url"))  # 下载
            content = downloadresp.content
            server.stop()  # 婴儿般的睡眠
            server.wait_for_start()
            # 写入本地
            Modfile_path = os.path.join(mods_path, response[0].get("files")[0].get("filename"))
            with open(Modfile_path, "wb+") as f:
                f.write(content)
            ModFile_hash = calculate_hash(Modfile_path)
            if (ModFile_hash == response[0].get("files")[0].get("hashes").get("sha1")):  # sha1检测
                server.logger.info("Hash Pass!")
                if modFile_name != "None":
                    server.logger.info("Deleteing old mod file:" + os.path.join(mods_path, modFile_name))
                    os.remove(os.path.join(mods_path, modFile_name))  # 删除旧的

    except requests.exceptions.Timeout:
        server.logger.info(server.tr("reden-update-check.timed_out"))  # 超时


def on_load(server: PluginServerInterface, old):
    server.logger.info(server.tr("reden-update-check.hello"))

    with open("config.yml", "r") as file_handler:
        mcdr_config_data = yaml.load(file_handler, Loader=Loader)  # 读mcdr配置，防止有人改了工作目录
    mods_path = os.path.join(mcdr_config_data["working_directory"], "mods")

    ModList = GetModfileList(mods_path)
    server.logger.info(server.tr("reden-update-check.mods") + str(ModList))

    modFile_name = find_mod_file(ModList, mods_path)  # 查找模组文件
    if modFile_name is not None:  # 找到了模组文件
        server.logger.info(server.tr("reden-update-check.foundmod") + modFile_name)

    @new_thread("Update Reden")
    def updateReden():
        download_and_shutdown(server, modFile_name, mods_path)  # 下载并替换模组文件
        server.start()  # 打开服务器

    updateReden()  # 更新