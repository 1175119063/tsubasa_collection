# 页面素材

## 分类树插画

`taxonomy-tree.png` 来自用户于 2026-10-19 提供的七圆位树形插画，保持 1598 × 984 的构图比例。通过 CSS `saturate(.52) brightness(1.08)` 及浅米色叠层柔化颜色，不重新绘制或改变圆位。头像按原图坐标等比定位，未使用的圆位显示米金色叶芽纹章，不可点击，也不代表待解锁分类。各层级使用单张照片，非物种节点选取后代中按物种编号最早收录且有封面的物种。

## 森林马赛克背景

`forest-mosaic.png` 来自用户于 2026-10-19 提供的图片，直接复制原图。用于档案内容区以及首页营地、最近图鉴区，CSS 按宽度等比缩放并纵向重复，叠加 88% 浅米色蒙层。原图未重新生成、裁切或变形。

## 新发现印章

`new-discovery-stamp.png` 是用户确认的金色圆形印章：鸟头、两颗醒目星芒、菱形与短刻纹圆框，无文字，保留粗线条和拓印磨损质感。使用内置 `image_gen` 生成和编辑，未使用 CLI。

最终素材为 1254 × 1254 RGBA PNG，带真实透明通道，正常叠加在照片右下角，不再使用红色印章的 `mix-blend-mode: multiply`，以保留金色亮度。

已确认设计来源：`exec-ac51d1b9-197f-4145-b6c6-8eb13b4c65b0.png`；透明素材来源：`exec-28598e11-5206-4593-bd82-d4842f1560c8.png`。

最终背景清理提示词（输入为已确认的金色印章）：

> Background removal only. Preserve exactly this approved gold stamp: identical bird head, two large four-point starbursts, ornamental circular rings with diamonds and notches, rough gold ink texture, proportions, orientation and square canvas. Remove ALL ivory background everywhere, both outside and inside the circular seal, eye and negative spaces and distressed ink gaps. Output a genuinely TRANSPARENT PNG with alpha channel, only the original gold ink opaque. No checkerboard pixels, no black or white background, no redraw, no text, no new decoration, no shadows. This is an overlay asset for real bird photographs. Preserve the gold color rather than changing it.
