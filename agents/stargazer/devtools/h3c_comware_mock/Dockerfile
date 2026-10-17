FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    H3C_MOCK_FIXTURE_DIR=/opt/h3c_comware_mock/fixtures

RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-server python3 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /var/run/sshd /opt/h3c_comware_mock

COPY comware_cli.py /opt/h3c_comware_mock/comware_cli.py
COPY fixtures /opt/h3c_comware_mock/fixtures
COPY sshd_config /etc/ssh/sshd_config

# Creds: username admin / password Admin@h3c
# Login shell lives next to fixtures so SSH (which drops image ENV) still finds them.
RUN chmod 755 /opt/h3c_comware_mock/comware_cli.py \
    && ln -sf /opt/h3c_comware_mock/comware_cli.py /usr/local/bin/comware_cli \
    && grep -qxF /opt/h3c_comware_mock/comware_cli.py /etc/shells || echo /opt/h3c_comware_mock/comware_cli.py >> /etc/shells \
    && useradd -m -s /opt/h3c_comware_mock/comware_cli.py admin \
    && echo 'admin:Admin@h3c' | chpasswd \
    && touch /home/admin/.hushlogin \
    && chown admin:admin /home/admin/.hushlogin \
    && ssh-keygen -A \
    && sed -i '/pam_motd/s/^/#/' /etc/pam.d/sshd \
    && sed -i '/pam_lastlog/s/^/#/' /etc/pam.d/sshd

EXPOSE 22

CMD ["/usr/sbin/sshd", "-D", "-e"]
