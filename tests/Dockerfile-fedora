FROM fedora:latest

ENV container docker

RUN dnf -y update \
    && dnf -y install systemd \
    && dnf clean all

RUN cd /lib/systemd/system/sysinit.target.wants/; \
    for i in *; do [ $i = systemd-tmpfiles-setup.service ] || rm -f $i; done

RUN rm -f /lib/systemd/system/multi-user.target.wants/* \
    /etc/systemd/system/*.wants/* \
    /lib/systemd/system/local-fs.target.wants/* \
    /lib/systemd/system/sockets.target.wants/*udev* \
    /lib/systemd/system/sockets.target.wants/*initctl* \
    /lib/systemd/system/basic.target.wants/* \
    /lib/systemd/system/anaconda.target.wants/*

# Nginx
RUN dnf update -y && \
    dnf install -y curl gnupg2 ca-certificates redhat-lsb-core python3-pip && \
    dnf install nginx-1.20.2 -y

VOLUME [ "/sys/fs/cgroup" ]

CMD ["/usr/sbin/init"]