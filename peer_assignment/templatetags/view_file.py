import os
import codecs
from django import template
from django.conf import settings
from peer_home.utils import merge_dicts

register = template.Library()


@register.inclusion_tag("view-file.html")
def view_file(file_field, header="", important=False):
    render_dict = {"header": header, "tag": "h3" if important else "h5"}
    if file_field is None:
        render_dict["file_not_found"] = True
        return render_dict

    file_path = os.path.join(settings.MEDIA_ROOT, file_field.name)

    if not os.path.isfile(file_path):
        render_dict["file_not_found"] = True
        return render_dict

    render_dict["url"] = file_field.url

    try:
        file_name = os.path.basename(file_field.file.name)
    except:
        render_dict["cant_read"] = True
        return render_dict

    ext = file_name.split(".")[-1]

    if ext == "pdf":
        return merge_dicts(render_dict, {"is_pdf": True})
    elif ext in settings.LANGUAGE_EXT_TO_NAME:
        try:
            content = codecs.open(file_path, encoding="utf-8").read()
        except:
            content = ""
            render_dict["cant_read"] = True
        return merge_dicts(
            render_dict,
            {
                "display_code": True,
                "language": settings.LANGUAGE_EXT_TO_NAME[ext],
                "content": content,
            },
        )
    else:
        return render_dict
