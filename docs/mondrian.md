# Redmi K60（mondrian）追梦 24.7.28

设备工作流以 WildKernels r23 为基础，构建 `5.10.198-android12-9`、ARM64、4 KiB 页的内核。Android common 源码固定为 `android12-5.10-2023-11_r2` 的 `226a9632f13d26e93fa416f6b003712b69118322`。KernelSU-Next、SUSFS、NoMount 和内核补丁的提交记录在工作流中。[构建配置](../.github/workflows/mondrian.yml)

1. 在 GitHub Actions 打开 **Redmi K60 mondrian**，选择 `mondrian-5.10.198` 分支并运行。完成后下载名称以 `AnyKernel3` 结尾的 ZIP。
2. 在电脑上从追梦纯净版 24.7.28 的 ROM 包提取 `images/miboot.img`。其 SHA-256 为 `5f038cb4cb71985be5c358aa8ec8e21db52ee41f90d738e73c21559876c20f94`。同包的 `images/boot.img` 自带 Magisk Delta。
3. 准备 Python 3.11 或更新版本，以及 Android 14 的 AOSP 封装工具。保留 `mkbootimg.py` 同仓库中的 `gki/` 目录。[mkbootimg 源码](https://android.googlesource.com/platform/system/tools/mkbootimg/+/refs/tags/android-14.0.0_r1/) · [avbtool 源码](https://android.googlesource.com/platform/external/avb/+/refs/tags/android-14.0.0_r1/avbtool.py)
4. 将命令中的路径替换为实际文件路径，在本地封装。

```shell
python tools/mondrian_boot.py --stock miboot.img --kernel-zip AnyKernel3.zip --mkbootimg mkbootimg/mkbootimg.py --avbtool avb/avbtool.py --output boot-mondrian.img
```

脚本保留纯净镜像的 ramdisk，核对 boot v4 头和分区尺寸，按原包格式重新计算外层 AVB 哈希。个人内核使用无 Google GKI 证书的自定义启动镜像，适用于已解锁的设备。保留原始 `miboot.img`，用 `fastboot boot boot-mondrian.img` 临时启动后再验证管理器、触控、相机、通话和 Wi‑Fi。
