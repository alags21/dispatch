FROM forgeops-sandbox:local
USER root
RUN python -m venv /opt/semgrep && /opt/semgrep/bin/pip install --no-cache-dir semgrep==1.185.0 && ln -s /opt/semgrep/bin/semgrep /usr/local/bin/semgrep
COPY security.yml /opt/forgeops/security.yml
RUN chmod 755 /opt/forgeops && chmod 644 /opt/forgeops/security.yml
USER 65534:65534
