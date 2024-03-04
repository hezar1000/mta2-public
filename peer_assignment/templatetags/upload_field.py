from django import template

register = template.Library()


@register.inclusion_tag("upload-field.html")
def upload_field(name, file=None, label="", tooltip="Only PDF files are allowed"):
    return {
        "name": name,
        "file": file,
        "has_file": file is not None,
        "label": label,
        "tooltip": tooltip,
    }
