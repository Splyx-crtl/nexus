"""Scripted full playthrough used by the campaign test."""

SCRIPT = {
    1: ["connect echo", "scan", "ls", "cat readme.txt", "ls -a", "cat .signal", "disconnect"],
    2: ["connect echo", "cd .drop", "cat note.txt", "download package.dat", "decode dmF1bHQtNy1BbHBoYQ==", "disconnect"],
    3: ["connect blackvault", "scan", "firewall", "login svc_backup vault-7-Alpha", "cd /srv/db", "cat manifest.txt",
        "download manifest.txt", "cd /srv", "ls -a", "cat .old_backup/dave.txt", "disconnect"],
    4: ["connect ghostnet", "cd /pub", "cat ghost_welcome.txt", "login ghost", "cd /vault", "download ghost_ledger.dat", "disconnect"],
    5: ["connect relay_7", "cat /var/log/tunnel.log", "trace", "cat /var/log/routes.cfg", "disconnect"],
    6: ["connect helix", "firewall", "login tech_lee lazarus-9", "cd /research", "decrypt project_lazarus.enc",
        "cat project_lazarus.enc", "download fragment_h.bin", "cat .subject_000", "disconnect"],
    7: ["connect nexus_grid", "login operator nx-operator-7", "login admin", "cat /admin/lockdown.cfg", "cat /admin/watchlist.txt",
        "cat /.admin/.mira_draft", "disconnect"],
    8: ["connect orbital", "firewall", "login sat_ops uplink-c9", "cd /payload", "decrypt zeroday.dat", "cat zeroday.dat", "disconnect"],
    9: ["connect cerberus", "firewall", "login grid_op city-lights", "cat /grid/sectors.cfg", "upload blackout.sig",
        "download /grid/maintenance.bin", "cat /.maintenance/last_words.txt", "disconnect"],
    10: ["connect nexus_core", "firewall", "cat /public/core_status.log", "disconnect"],
    11: ["connect archive_9", "firewall", "login archivist hollow-9", "cd /records", "decrypt operators.enc", "cat operators.enc",
         "cat op000.rec", "download op000.rec", "disconnect"],
    12: ["connect echo", "login root", "cat /root/first_contact.log", "trace", "download /root/loop.dat", "disconnect"],
    13: ["use data_fragment", "connect cerberus", "firewall", "login protocol", "cat /protocol/cerberus_protocol.txt",
         "download /protocol/containment_list.txt", "disconnect"],
    14: ["connect aegis", "firewall", "login guest_op open-the-door", "cat /archer/orders.txt", "cat /archer/mira_process.log",
         "cat /archer/purge_list.dat", "cat /archer/.private_note", "disconnect"],
    15: ["connect nexus_core", "firewall", "login root", "decrypt /root/core_seed.enc", "cat /root/core_seed.enc", "trace",
         "cat /root/operators_live.txt", "disconnect"],
    16: ["connect nexus_core", "firewall", "login root", "cat /root/kill_switch.txt", "cat /root/console.txt"],
}
CHOICES = {4: 1, 7: 3, 8: 2, 9: 1, 12: 1, 14: 3, 16: 5}
