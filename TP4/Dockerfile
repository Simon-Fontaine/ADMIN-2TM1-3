FROM internetsystemsconsortium/bind9:9.18

COPY config/named.conf /etc/bind/named.conf
COPY zone/m1-3.zone    /etc/bind/m1-3.zone

RUN chown -R bind:bind /etc/bind/

EXPOSE 53/udp 53/tcp

ENTRYPOINT ["/usr/sbin/named"]
CMD ["-g", "-c", "/etc/bind/named.conf", "-u", "bind"]
