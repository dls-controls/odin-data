import re


def remove_prefix(string, prefix):
    return re.sub("^{}".format(prefix), "", string)


def remove_suffix(string, suffix):
    return re.sub("{}$".format(suffix), "", string)


MAJOR_VER_REGEX = r"^([0-9]+)[\\.-].*|$"
MINOR_VER_REGEX = r"^[0-9]+[\\.-]([0-9]+).*|$"
PATCH_VER_REGEX = r"^[0-9]+[\\.-][0-9]+[\\.-]([0-9]+).|$"


def construct_version_dict(full_version):
    major_version = re.findall(MAJOR_VER_REGEX, full_version)[0]
    minor_version = re.findall(MINOR_VER_REGEX, full_version)[0]
    patch_version = re.findall(PATCH_VER_REGEX, full_version)[0]
    short_version = major_version + "." + minor_version + "." + patch_version

    return dict(
        full=full_version,
        major=major_version,
        minor_version=minor_version,
        patch_version=patch_version,
        short_version=short_version,
    )
