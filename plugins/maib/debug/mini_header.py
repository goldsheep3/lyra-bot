import os, sys

os.environ["MAIB_IMAGE_GEN_DEBUG"] = "1"
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ===============================


if __name__ == "__main__":
    # 绝对导入
    from plugins.maib.debug import public_data
    
    
    from plugins.maib.image_gen._components.b50_box import B50BoxBadge

    result_img = B50BoxBadge.header_box(dxrating=10059, latest_version=21, is_b15=False, cirp_frame=True)
    result_img.show()
