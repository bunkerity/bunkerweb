import os, stat

def has_permissions(path, need_permissions) :
    uid = os.geteuid()
    gid = os.getegid()
    statinfo = os.stat(path)
    permissions = {"R": False, "W": False, "X": False}
    if statinfo.st_uid == uid :
        if statinfo.st_mode & stat.S_IRUSR :
            permissions["R"] = True
        if statinfo.st_mode & stat.S_IWUSR :
            permissions["W"] = True
        if statinfo.st_mode & stat.S_IXUSR :
            permissions["X"] = True
    if statinfo.st_uid == gid :
        if statinfo.st_mode & stat.S_IRGRP :
            permissions["R"] = True
        if statinfo.st_mode & stat.S_IWGRP :
            permissions["W"] = True
        if statinfo.st_mode & stat.S_IXGRP :
            permissions["X"] = True
    if statinfo.st_mode & stat.S_IROTH :
        permissions["R"] = True
    if statinfo.st_mode & stat.S_IWOTH :
        permissions["W"] = True
    if statinfo.st_mode & stat.S_IXOTH :
        permissions["X"] = True
    list_permissions = [permission for permission in need_permissions]
    for need_permission in list_permissions :
        if not permissions[need_permission] :
            return False
    return True