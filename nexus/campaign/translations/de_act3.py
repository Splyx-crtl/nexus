"""German translation, Act III — The Network (levels 46-70). Third block of docs/3.0-PROGRESS.md's "translate one
act at a time" plan. Covers all 25 missions. See de_act1.py's module docstring for the general approach (English
stays authoritative, solution lines are never translated). Oduya's pronouns are never stated in the English source,
so lines referring to them stay pronoun-free in German too (repeating "Oduya" instead of a gendered "sie"/"er").
"""
from __future__ import annotations

from ..i18n import register

register(
    "act3_m46", "de",
    title="Immer noch da",
    briefing=["NEXUS: Bisher war alles aus zweiter Hand — Protokolle, Login-Historien, jemand anderes Dossier. "
              "Zeit, selbst nachzusehen. Ist es überhaupt noch da?"],
    debrief=["NEXUS: Lebendig, antwortet, versucht sich nicht mal zu verstecken. Selbstsicher, oder nachlässig. "
             "Wir werden sehen, was es ist."],
    objectives=[{"text": "203.0.113.9 direkt anpingen",
                "hints": ["ping bestätigt, dass eine Maschine tatsächlich erreichbar ist.", "Versuch: ping 203.0.113.9", "ping 203.0.113.9"]}],
)

register(
    "act3_m47", "de",
    title="Einen Namen dazu finden",
    briefing=["MIRA: Wenn diese Adresse jemandem gehört, hat sie irgendwo einen Namen dranstehen. Finde ihn."],
    debrief=["MIRA: nexus-company.com. Dieselbe Firma, dieselbe Adresse, kein Zufall mehr zu bestreiten."],
    objectives=[{"text": "nexus-company.com auflösen (dig)",
                "hints": ["dig übersetzt einen Domainnamen in eine Adresse.", "Versuch: dig nexus-company.com", "dig nexus-company.com"]}],
)

register(
    "act3_m48", "de",
    title="Papierspur",
    briefing=["NEXUS: Bevor du weitergehst — wem gehört diese Domain eigentlich, und seit wann?"],
    debrief=["NEXUS: 2031. Neunzehn Jahre vor allem hier. Was auch immer das ist, es ist keine spontane Entscheidung."],
    objectives=[{"text": "Die Registrierung der Domain prüfen (whois)",
                "hints": ["whois zeigt, wer eine Domain registriert hat und seit wann.", "Versuch: whois nexus-company.com", "whois nexus-company.com"]}],
)

register(
    "act3_m49", "de",
    title="Die eigene Position kennen",
    briefing=["MIRA: Bevor du in irgendjemandes Netzwerk herumstocherst, kenn dein eigenes. Was ist deine Adresse, "
              "und was sonst noch auf diesem Segment mit dir?"],
    debrief=["MIRA: Gut. Wisse immer, wie du von außen aussiehst, bevor du dir jemand anderen ansiehst."],
    objectives=[
        {"text": "Deine eigene Netzwerkadresse prüfen (ip addr)",
         "hints": ["ip addr zeigt die eigenen Schnittstellen und Adressen dieser Maschine.", "Versuch: ip addr", "ip addr"]},
        {"text": "Sehen, wer sonst in deinem lokalen Netzwerk ist (arp -a)",
         "hints": ["arp -a listet Maschinen, mit denen du kürzlich in diesem Netzwerk gesprochen hast.", "Versuch: arp -a", "arp -a"]},
    ],
)

register(
    "act3_m50", "de",
    title="Die alte Hand",
    briefing=["NEXUS: Mira hat jemand anderen gebeten, sich das anzusehen, bevor du weitermachst. Lies es."],
    debrief=["NEXUS: 'Langweiliger Fußabdruck.' Damit kann ich arbeiten.",
             "MIRA: Oduya macht das schon länger als wir beide zusammen. Hör zu, wenn Oduya sich die Mühe macht, "
             "etwas zu sagen."],
    objectives=[{"text": "Oduyas Nachricht lesen",
                "hints": ["Schau in deinen Posteingang.", "Versuch: cat inbox/oduya_intro.txt", "cat inbox/oduya_intro.txt"]}],
)

register(
    "act3_m51", "de",
    title="Was zu sehen ist",
    briefing=["NEXUS: Sehen wir, was es einem Fremden zeigen will. Zieh die Startseite."],
    debrief=["NEXUS: 'Nur für internen Gebrauch' — auf einer Seite, die jeder im Internet laden kann. Das ist nicht intern."],
    objectives=[{"text": "Die Startseite des Servers abrufen (curl)",
                "hints": ["curl lädt alles herunter, was eine Webadresse liefert, direkt ins Terminal.",
                         "Versuch: curl http://nexus-company.com/", "curl http://nexus-company.com/"]}],
)

register(
    "act3_m52", "de",
    title="Offen liegen gelassen",
    briefing=["MIRA: Versuch zuerst das Offensichtliche. changelog.txt, robots.txt, solche Sachen — Leute vergessen, "
              "dass die auch öffentlich sind."],
    debrief=["MIRA: 'Relais für Diagnosezwecke wieder aktiviert — vorübergehend.' Am selben Tag, an dem diese "
             "Adresse in unseren Protokollen auftauchte. Auch das ist kein Zufall."],
    objectives=[
        {"text": "Das Änderungsprotokoll herunterladen (wget)",
         "hints": ["wget speichert eine Datei, statt sie nur anzuzeigen.", "Versuch: wget http://nexus-company.com/changelog.txt",
                  "wget http://nexus-company.com/changelog.txt"]},
        {"text": "Lesen, was du herunterladen hast",
         "hints": ["Es wurde unter seinem eigenen Namen im aktuellen Ordner gespeichert.", "Versuch: cat changelog.txt", "cat changelog.txt"]},
    ],
)

register(
    "act3_m53", "de",
    title="Das ganze Bild",
    briefing=["NEXUS: Letzte Sache, bevor Oduyas Regeln wirklich greifen: was läuft eigentlich, auf deiner Box und "
              "auf dem Weg zwischen dir und ihnen?"],
    debrief=["NEXUS: Dein eigenes ssh steht jedem offen, der dich zuerst findet — merken, nicht heutiges Problem. "
             "Und der Weg zu diesem Server ist kurz. Zu kurz für etwas, das angeblich 'intern' ist.",
             "MIRA: Kapitel geschlossen. Wir wissen, dass es real ist, wir wissen, wem es gehört, und wir wissen "
             "ungefähr, was darauf läuft. Nächstes Kapitel schauen wir nicht mehr nur von außen."],
    objectives=[
        {"text": "Prüfen, was auf deiner eigenen Maschine lauscht (netstat)",
         "hints": ["netstat listet Netzwerkverbindungen und lauschende Ports auf dieser Maschine.", "Versuch: netstat -tulpn", "netstat -tulpn"]},
        {"text": "Mit dem modernen Werkzeug nochmal prüfen (ss)",
         "hints": ["ss ist der moderne Ersatz für netstat.", "Versuch: ss -tulpn", "ss -tulpn"]},
        {"text": "Den Weg zum Ziel nachzeichnen (traceroute)",
         "hints": ["traceroute zeigt jede Zwischenstation zwischen dir und einem Ziel.", "Versuch: traceroute 203.0.113.9", "traceroute 203.0.113.9"]},
    ],
)

register(
    "act3_m54", "de",
    title="Zwei weitere Arten zu fragen",
    briefing=["MIRA: Vertrau nicht der Antwort eines einzigen Werkzeugs, wenn es drei gibt, die dieselbe Frage "
              "anders stellen. Bestätige es auch mit nslookup und host."],
    debrief=["MIRA: Dieselbe Antwort, dreimal. Gut. Jetzt vertraust du ihr tatsächlich, statt sie nur zu glauben."],
    objectives=[
        {"text": "nexus-company.com auflösen (nslookup)",
         "hints": ["nslookup ist ein älteres, einfacheres DNS-Abfragewerkzeug.", "Versuch: nslookup nexus-company.com", "nslookup nexus-company.com"]},
        {"text": "Noch einmal auflösen (host)",
         "hints": ["host gibt dieselbe Antwort im einfachsten Format aller drei.", "Versuch: host nexus-company.com", "host nexus-company.com"]},
    ],
)

register(
    "act3_m55", "de",
    title="Der ältere Weg",
    briefing=["NEXUS: Manche Systeme haben nur noch das alte Werkzeug installiert. Prüf deine eigenen Schnittstellen "
              "auf die altmodische Art."],
    debrief=["NEXUS: Dieselbe Information, die ip addr dir gegeben hat, nur anders formatiert. Kenn beide — du "
             "wirst nicht immer wählen können."],
    objectives=[{"text": "Deine Schnittstellen auf die alte Art prüfen (ifconfig)",
                "hints": ["ifconfig ist älter als ip und zeigt dieselbe Art von Information.", "Versuch: ifconfig", "ifconfig"]}],
)

register(
    "act3_m56", "de",
    title="Die Robots prüfen",
    briefing=["NEXUS: Jede Seite hat eine Datei, die Suchmaschinen sagt, was sie nicht durchsuchen sollen. Eine "
              "höfliche Bitte, kein Schloss — und meistens der erste Ort, der sich lohnt."],
    debrief=["NEXUS: 'Disallow: /ops-console/.' Sie haben uns genau gesagt, wo wir nachsehen sollen."],
    objectives=[{"text": "robots.txt prüfen",
                "hints": ["Es ist nur ein weiterer Pfad auf demselben Server.", "Versuch: curl http://nexus-company.com/robots.txt",
                         "curl http://nexus-company.com/robots.txt"]}],
)

register(
    "act3_m57", "de",
    title="Durch die unverschlossene Tür",
    briefing=["MIRA: Jetzt weißt du, wo du nachsehen musst. Sieh, was tatsächlich da ist, und wenn etwas "
              "herunterladbar ist, lade es herunter und lies es richtig."],
    debrief=["MIRA: Lebende Deploy-Zugangsdaten. In einer Konfigurationsdatei. Auf einem Pfad, den sie mit einer "
             "reinen Bitte-nicht-Textdatei zu verstecken versuchten.",
             "NEXUS: Das ist keine Technik. Das ist einfach jemand, der vergessen hat, eine Tür abzuschließen."],
    objectives=[
        {"text": "Sehen, was im ops-console-Pfad ist",
         "hints": ["Gleicher Schritt wie robots.txt, anderer Pfad.", "Versuch: curl http://nexus-company.com/ops-console/",
                  "curl http://nexus-company.com/ops-console/"]},
        {"text": "backup.cfg herunterladen",
         "hints": ["wget speichert sie lokal, statt sie nur anzuzeigen.", "Versuch: wget http://nexus-company.com/ops-console/backup.cfg",
                  "wget http://nexus-company.com/ops-console/backup.cfg"]},
        {"text": "Lesen, was du herunterladen hast",
         "hints": ["Es wurde unter seinem eigenen Namen gespeichert.", "Versuch: cat backup.cfg", "cat backup.cfg"]},
    ],
)

register(
    "act3_m58", "de",
    title="Gefunden, nicht verdient",
    briefing=["NEXUS: Oduya schon wieder. Diese hier lohnt sich, langsam zu lesen."],
    debrief=["NEXUS: Was auch immer du ihnen gesagt hast — ich hab bemerkt, dass du diesmal tatsächlich "
             "nachgedacht hast, statt einfach das Erste zu tippen, was dir in den Kopf kam.",
             "MIRA: Das ist der Job. Guter Instinkt, im Zaum gehalten. Behalte beides."],
    objectives=[
        {"text": "Oduyas Nachricht lesen", "hints": ["Schau in deinen Posteingang.", "Versuch: cat inbox/oduya_caution.txt", "cat inbox/oduya_caution.txt"]},
        {"text": "Ehrlich antworten",
         "hints": ["Gleicher Schritt wie zuvor — schreiben, an die Datei anhängen.",
                  'echo "deine Antwort hier" >> inbox/oduya_caution.txt', 'echo "Ich werde vorsichtig sein." >> inbox/oduya_caution.txt']},
    ],
)

register(
    "act3_m59", "de",
    title="Ein Name, der nicht antwortet",
    briefing=["NEXUS: Diese Konfiguration erwähnte eine Konsole auf einer Subdomain. Finde sie — sowohl die "
              "Adresse als auch, wer dahintersteckt."],
    debrief=["NEXUS: Sie löst auf. Wir sind trotzdem nirgends in ihrer Nähe — diese Adresse liegt auf keinem Pfad, "
             "den wir von hier erreichen können. Einen Namen einer Adresse zuzuordnen heißt nicht, dorthin zu kommen.",
             "MIRA: Merken. Wir kommen darauf zurück."],
    objectives=[
        {"text": "ops.nexus-company.com auflösen",
         "hints": ["Gleiches Werkzeug, diesmal ein anderer Name.", "Versuch: dig ops.nexus-company.com", "dig ops.nexus-company.com"]},
        {"text": "Prüfen, wer sie registriert hat",
         "hints": ["whois funktioniert auch bei Subdomains.", "Versuch: whois ops.nexus-company.com", "whois ops.nexus-company.com"]},
    ],
)

register(
    "act3_m60", "de",
    title="Was es freiwillig verrät",
    briefing=["MIRA: Bevor wir mit diesem Server erstmal fertig sind — was sagt er über sich selbst, ohne gefragt "
              "zu werden? Nur die Header, sonst nichts."],
    debrief=["MIRA: nginx, mit Versionsnummer. Für später vermerkt — das wird wichtig, wenn wir nach Schwachstellen "
             "suchen statt nur nach Türen."],
    objectives=[{"text": "Die Header des Servers abrufen (curl -I)",
                "hints": ["-I ruft nur die Header ab, nicht die Seite selbst.", "Versuch: curl -I http://nexus-company.com/",
                         "curl -I http://nexus-company.com/"]}],
)

register(
    "act3_m61", "de",
    title="Alles, was dieses Kapitel gefunden hat",
    briefing=["MIRA: Zieh jede nach Zugangsdaten aussehende Zeichenkette, die du dieses Kapitel gefunden hast, in "
              "eine Datei, und archiviere eine Kopie, bevor wir weitermachen."],
    debrief=["MIRA: Abgelegt und gesperrt. Kapitel geschlossen.",
             "NEXUS: Das nächste Mal, wenn wir diesen Server anfassen, ist es nicht mehr von außen."],
    objectives=[
        {"text": "Die Funde zusammenstellen und prüfen (grep -r ... | tee)",
         "hints": ["Gleicher Trick wie Akt IIs Fallakte — suchen, und eine Kopie speichern, während du hinschaust.",
                  "Versuch: grep -r DEPLOY recon | tee creds_summary.txt", "grep -r DEPLOY recon | tee creds_summary.txt\ncat creds_summary.txt"]},
        {"text": "Eine Kopie dort archivieren, wo nur root hinkommt (sudo cp)",
         "hints": ["Derselbe Archiv-Ordner wie vorher — nur root, und er liegt unter /archive, nicht in deinem Home-Ordner.",
                  "Versuch: sudo cp creds_summary.txt /archive/creds_summary.txt", "sudo cp creds_summary.txt /archive/creds_summary.txt"]},
    ],
)

register(
    "act3_m62", "de",
    title="Erster Login",
    briefing=["MIRA: Du hast jetzt ein funktionierendes Passwort. Benutz es. sshpass gibt es an ssh weiter, ohne "
              "eine Eingabeaufforderung zu zeigen — so skriptet man einen Login, statt ihn jedes Mal von Hand "
              "einzutippen."],
    debrief=["MIRA: Du bist drin. Mach dich nicht zu bequem — von jetzt an gelten Oduyas Regeln, wirklich."],
    objectives=[{"text": "Als deploy auf den Edge-Server einloggen",
                "hints": ["sshpass -p PASSWORT ssh benutzer@host loggt ohne interaktive Eingabeaufforderung ein.",
                         "Versuch: sshpass -p n3xus-deploy! ssh deploy@nexus-company.com", "sshpass -p n3xus-deploy! ssh deploy@nexus-company.com"]}],
)

register(
    "act3_m63", "de",
    title="Neuer Boden",
    briefing=["NEXUS: Gleiche Befehle, andere Maschine. Finde heraus, was hier eigentlich drauf ist, bevor "
              "irgendwas anderes passiert."],
    debrief=["NEXUS: Ein Relais-Dienst, offenbar von einer Deploy-Pipeline verwaltet. Noch nichts Ungewöhnliches."],
    objectives=[
        {"text": "Finden, was unter /srv liegt (find /srv -type f)",
         "hints": ["find funktioniert auf einer entfernten Maschine genau wie lokal, sobald du eingeloggt bist.", "Versuch: find /srv -type f", "find /srv -type f"]},
        {"text": "Das README des Relais lesen",
         "hints": ["Es liegt unter /srv/relay.", "Versuch: cat /srv/relay/README.txt", "cat /srv/relay/README.txt"]},
    ],
)

register(
    "act3_m64", "de",
    title="Nicht so privilegiert",
    briefing=["MIRA: Bevor du annimmst, dass du dort alles darfst — prüf nach. Worauf hat deploy tatsächlich Rechte?"],
    debrief=["MIRA: Nichts. Ein Dienstkonto, genau so privilegiert, wie es sein muss, und keinen Deut mehr. So "
             "soll es funktionieren, für einmal."],
    objectives=[{"text": "Prüfen, was deploy als root ausführen kann (sudo -l)",
                "hints": ["sudo -l listet, was du ausführen darfst — falls überhaupt etwas.", "Versuch: sudo -l", "sudo -l"]}],
)

register(
    "act3_m65", "de",
    title="Ein Wort, das NEXUS nicht mag",
    briefing=["NEXUS: Prüf das eigene Protokoll des Relais. Protokolle sagen dir, was ein Ding tatsächlich tut, "
              "nicht was sein README behauptet."],
    debrief=["NEXUS: 'ARCHITECT-NEXUS-Abgleich.' ...Dazu fällt mir gerade kein schlauer Spruch ein. Gib mir einen Moment.",
             "MIRA: NEXUS? Du bist still geworden.",
             "NEXUS: Mir geht's gut. Mach weiter. Wir kommen darauf zurück."],
    objectives=[{"text": "Das eigene Protokoll des Relais lesen",
                "hints": ["Gleicher Ordner wie das README.", "Versuch: cat /srv/relay/relay.log", "cat /srv/relay/relay.log"]}],
)

register(
    "act3_m66", "de",
    title="Eine Kopie nehmen",
    briefing=["MIRA: Hol dir eine Kopie dieses Protokolls von ihrer Maschine auf deine. Ich will sie irgendwo, wo "
              "sie es nicht später still bearbeiten können."],
    debrief=["MIRA: Abgelegt. Wenn diese Zeile morgen von ihrem Server verschwindet, haben wir sie trotzdem noch."],
    objectives=[
        {"text": "relay.log auf deine eigene Maschine kopieren (scp)",
         "hints": ["scp funktioniert wie cp, nur dass eine Seite ein entfernter Host sein kann.",
                  "Versuch: sshpass -p n3xus-deploy! scp deploy@nexus-company.com:/srv/relay/relay.log relay.log",
                  "sshpass -p n3xus-deploy! scp deploy@nexus-company.com:/srv/relay/relay.log relay.log"]},
        {"text": "Bestätigen, dass es richtig kopiert wurde",
         "hints": ["Lies sie lokal zurück.", "Versuch: cat relay.log", "cat relay.log"]},
    ],
)

register(
    "act3_m67", "de",
    title="Wer ist sonst noch auf dieser Maschine",
    briefing=["NEXUS: Gleiche Gewohnheit wie immer, nur diesmal woanders hingerichtet: was läuft, und wer ist "
              "eingeloggt?"],
    debrief=["NEXUS: 'telemetry-shim, --passthrough', läuft als root. Könnte nichts sein. Könnte auch genau der "
             "Grund sein, warum diese Adresse so geduldig war. Nicht deine Box zum Aufräumen — noch nicht. Nur merken."],
    objectives=[
        {"text": "Prüfen, was auf der Relais-Box läuft (ps aux)", "hints": ["Gleicher Befehl, fremde Maschine.", "Versuch: ps aux", "ps aux"]},
        {"text": "Prüfen, wer sonst eingeloggt ist (who)", "hints": ["who zeigt jede aktive Sitzung auf dieser Maschine.", "Versuch: who", "who"]},
    ],
)

register(
    "act3_m68", "de",
    title="Zurückkommen",
    briefing=["MIRA: Einloggen, bestätigen, dass du sauber wieder rauskommst, dann beweis es."],
    debrief=["MIRA: Gut. Wisse immer, dass du zurückkommen kannst, bevor du irgendwohin gehst, das sich lohnt."],
    objectives=[
        {"text": "Vom Edge-Server ausloggen (exit)",
         "hints": ["exit bringt dich zurück zu der Maschine, von der aus du dich verbunden hast.", "Versuch: exit", "exit"]},
        {"text": "Bestätigen, dass du wieder auf home-rig bist",
         "hints": ["Diese Datei existiert nur lokal.", "Versuch: cat welcome_back.txt", "cat welcome_back.txt"]},
    ],
)

register(
    "act3_m69", "de",
    title="Keines dieser Worte gefällt mir",
    briefing=["NEXUS: Mira will über das reden, was du gefunden hast. Lies es."],
    debrief=["NEXUS: Für was es wert ist — mir auch nicht.",
             "MIRA: Wir sind nicht fertig mit diesem Server. Wir sind nur fertig damit, ihn von außen zu betrachten."],
    objectives=[{"text": "Miras Reaktion lesen",
                "hints": ["Schau in deinen Posteingang.", "Versuch: cat inbox/mira_architect.txt", "cat inbox/mira_architect.txt"]}],
)

register(
    "act3_m70", "de",
    title="Drinnen, richtig",
    briefing=["MIRA: Letzter Durchgang. Einloggen, das Relais-Protokoll noch einmal für eine saubere Kopie ziehen, "
              "richtig archivieren, und wieder ausloggen. Nach Vorschrift, von Anfang bis Ende."],
    debrief=["MIRA: Saubere Arbeit. Rein, raus, dokumentiert, nichts zurückgelassen.",
             "NEXUS: Rangaufstieg — CRYPTOSMITH. Akt geschlossen. Nächstes Mal lesen wir nicht mehr ihre "
             "Infrastruktur von außen, sondern fangen an, das auseinanderzunehmen, was sie tatsächlich schützen.",
             "MIRA: Das heißt Schlüssel, Hashes, die Dinge, die Leute für unknackbar halten, weil noch nie jemand "
             "geduldig genug war, es zu versuchen."],
    objectives=[
        {"text": "Eine saubere Kopie von relay.log ziehen (scp)",
         "hints": ["Gleicher Schritt wie vorher.", "Versuch: sshpass -p n3xus-deploy! scp deploy@nexus-company.com:/srv/relay/relay.log relay.log",
                  "sshpass -p n3xus-deploy! scp deploy@nexus-company.com:/srv/relay/relay.log relay.log"]},
        {"text": "Sie dort archivieren, wo nur root hinkommt (sudo cp)",
         "hints": ["Gleiche Archiv-Gewohnheit wie Akt II — sie liegt unter /archive, nicht in deinem Home-Ordner.",
                  "Versuch: sudo cp relay.log /archive/relay.log", "sudo cp relay.log /archive/relay.log"]},
    ],
)
