"""German translation, Act II — Traces (levels 21-45). Second block of docs/3.0-PROGRESS.md's "translate one act at
a time" plan. Covers all 25 missions. See de_act1.py's module docstring for the general approach (English stays
authoritative, solution lines are never translated).
"""
from __future__ import annotations

from ..i18n import register

register(
    "act2_m21", "de",
    title="Zuschließen",
    briefing=["MIRA: Dieser Schlüssel ist gerade für jeden lesbar. Jeder auf dieser Maschine könnte ihn lesen. Sperr "
              "ihn auf dich selbst — Rechte 600, Besitzer lesen-schreiben, sonst niemand irgendwas."],
    debrief=["MIRA: Gut. Von jetzt an ist das der Standard — nichts bleibt für jeden lesbar, was es nicht muss."],
    objectives=[{"text": "vault.key auf Rechte 600 setzen",
                "hints": ["chmod 600 datei macht sie nur für den Besitzer lesbar und beschreibbar.", "Versuch: chmod 600 vault.key", "chmod 600 vault.key"]}],
)

register(
    "act2_m22", "de",
    title="Wessen Datei ist das",
    briefing=["MIRA: Unter /opt liegt eine übrig gebliebene Konfigurationsdatei, immer noch root gehörend. Die muss "
              "auf deinen Namen laufen, damit du damit arbeiten kannst. chown braucht sudo — chmod brauchte das "
              "nicht, das hier schon."],
    debrief=["MIRA: Das ist der Unterschied: chmod ändert, was eine Datei erlaubt, chown ändert, wem sie gehört. "
             "Das Zweite darf nur root entscheiden."],
    objectives=[
        {"text": "orphan.cfg zu deiner machen (chown, über sudo)",
         "hints": ["Nur root kann den Besitzer einer Datei ändern — dafür brauchst du sudo.",
                  "Versuch: sudo chown operator /opt/orphan.cfg", "sudo chown operator /opt/orphan.cfg"]},
        {"text": "sudo dafür benutzen",
         "hints": ["sudo führt einen Befehl als root aus.", "Versuch: sudo chown operator /opt/orphan.cfg", "sudo chown operator /opt/orphan.cfg"]},
    ],
)

register(
    "act2_m23", "de",
    title="Was nur root sehen kann",
    briefing=["MIRA: Alles, was ich über unsere anderen Kontakte weiß, steht in /etc/nexus_contacts.conf. Du hast "
              "keine Berechtigung, die einfach zu lesen — du musst dir die von root leihen."],
    debrief=["MIRA: sudo ist nicht nur für chown und chmod. Es heißt 'führ genau dieses eine Ding als root aus' — "
             "funktioniert für alles, cat eingeschlossen."],
    objectives=[
        {"text": "Die Kontaktdatei lesen (sudo cat)",
         "hints": ["Normales cat sagt 'Permission denied' — versuch's mit sudo.", "Versuch: sudo cat /etc/nexus_contacts.conf",
                  "sudo cat /etc/nexus_contacts.conf"]},
        {"text": "sudo dafür benutzen",
         "hints": ["sudo führt einen Befehl als root aus, egal welcher Befehl.", "Versuch: sudo cat /etc/nexus_contacts.conf",
                  "sudo cat /etc/nexus_contacts.conf"]},
    ],
)

register(
    "act2_m24", "de",
    title="Abschießen",
    briefing=["NEXUS: Deine Lüfter laufen seit einer Stunde auf Hochtouren, und du machst nichts. Irgendwas läuft, "
              "das nicht sollte. Finde es, dann stoppe es."],
    debrief=["NEXUS: 'xmr-helper.' Jemand hat auf deiner Hardware geschürft, auf deine Stromrechnung, ohne zu fragen.",
             "MIRA: Kleines Geld. Nervig, nicht gefährlich. Aber es bedeutet, dass mal etwas auf diese Maschine "
             "gekommen ist. Merken."],
    objectives=[
        {"text": "Nachsehen, was tatsächlich läuft (ps aux)",
         "hints": ["ps aux listet jeden laufenden Prozess mit Besitzer und PID.", "Versuch: ps aux", "ps aux"]},
        {"text": "Stoppen (kill 4821)", "hints": ["kill PID stoppt einen Prozess, sobald man seine Nummer kennt.", "Versuch: kill 4821", "kill 4821"]},
    ],
)

register(
    "act2_m25", "de",
    title="Wer ist sonst noch hier",
    briefing=["MIRA: Gewohnheit, die sich lohnt: nachsehen, wer gerade eingeloggt ist, und wer kürzlich eingeloggt "
              "war. Auch auf deiner eigenen Maschine. Besonders auf deiner eigenen Maschine."],
    debrief=["MIRA: Nichts Ungewöhnliches. Trotzdem weiter prüfen — das eine Mal, das du es auslässt, ist das Mal, "
             "an dem es zählt."],
    objectives=[
        {"text": "Nachsehen, wer gerade eingeloggt ist (who)", "hints": ["who zeigt jede gerade aktive Sitzung.", "Versuch: who", "who"]},
        {"text": "Die letzten Logins prüfen (last)", "hints": ["last zeigt eine Login-Historie, nicht nur die aktuelle.", "Versuch: last", "last"]},
    ],
)

register(
    "act2_m26", "de",
    title="Jemand anderes Spiel",
    briefing=["NEXUS: Jemand war vor dir bei job_007. Es wartet eine Notiz."],
    debrief=["NEXUS: 'Unerträglich zufrieden mit sich' trifft es wohl, einer einzigen Notiz nach zu urteilen.",
             "MIRA: Reyes ist nicht der Auftrag. Lass dich nicht ablenken, nur um einen Punkt zu beweisen — aber "
             "lass dir auch nicht auf der Nase herumtanzen."],
    objectives=[
        {"text": "Die hinterlassene Visitenkarte in job_007 lesen",
         "hints": ["In job_007 liegt eine Datei.", "Versuch: cat jobs/job_007/claimed.txt", "cat jobs/job_007/claimed.txt"]},
        {"text": "Miras Notiz dazu lesen, wer das war",
         "hints": ["Schau in deinen Posteingang.", "Versuch: cat inbox/about_reyes.txt", "cat inbox/about_reyes.txt"]},
    ],
)

register(
    "act2_m27", "de",
    title="Auf dem letzten Loch",
    briefing=["NEXUS: Die Platte füllt sich und ich weiß nicht, warum. Sieh nach, wie viel Platz noch da ist, dann "
              "finde, was ihn tatsächlich frisst."],
    debrief=["NEXUS: Ein Cache-Ordner, den eine Weile niemand aufgeräumt hat. Nichts Finsteres. Nur "
             "Vernachlässigung. Räum ihn auf, wenn du Zeit hast."],
    objectives=[
        {"text": "Nachsehen, wie viel Platz noch da ist (df)", "hints": ["df -h zeigt die Plattennutzung pro Dateisystem, menschenlesbar.", "Versuch: df -h", "df -h"]},
        {"text": "Finden, was den Platz frisst (du)", "hints": ["du -sh * misst alles im aktuellen Ordner.", "Versuch: du -sh .cache", "du -sh .cache"]},
    ],
)

register(
    "act2_m28", "de",
    title="Nicht, was es scheint",
    briefing=["MIRA: Diese Backup-Datei in deinem Arbeitsbereich ist keine echte Datei. Finde heraus, was sie "
              "wirklich ist, und wohin sie tatsächlich zeigt."],
    debrief=["MIRA: Ein Symlink nach /opt. Jemand wollte, dass es aussieht, als läge sie in deinem Arbeitsbereich, "
             "ohne tatsächlich dort zu sein. Guter Fang."],
    objectives=[
        {"text": "Herausfinden, was backup_link wirklich ist (file)",
         "hints": ["file verrät den echten Typ einer Datei, nicht nur ihren Namen.", "Versuch: file backup_link", "file backup_link"]},
        {"text": "Genau zeigen, wohin sie zeigt (readlink)",
         "hints": ["readlink gibt das echte Ziel eines Symlinks aus.", "Versuch: readlink backup_link", "readlink backup_link"]},
    ],
)

register(
    "act2_m29", "de",
    title="Hausputz",
    briefing=["NEXUS: Reine Neugier: wie lange läuft diese Maschine schon? Und wo bewahrt das System eigentlich "
              "die 'grep'-Programmdatei auf? Ich mag es, zu wissen, wo Dinge wohnen."],
    debrief=["NEXUS: Drei Tage, vier Stunden. Und /usr/bin, wie alles andere auch. Zufrieden. Weiter."],
    objectives=[
        {"text": "Nachsehen, wie lange die Maschine schon läuft (uptime)", "hints": ["uptime zeigt die Zeit seit dem letzten Start.", "Versuch: uptime", "uptime"]},
        {"text": "Finden, wo grep tatsächlich wohnt (whereis)",
         "hints": ["whereis zeigt die Speicherorte der Programmdatei und Handbuchseite eines Befehls.", "Versuch: whereis grep", "whereis grep"]},
    ],
)

register(
    "act2_m30", "de",
    title="Déjà Vu",
    briefing=["NEXUS: Es läuft etwas, das keiner von uns beiden gestartet hat. Voller Check — was läuft, wer sich "
              "eingeloggt hat, und sperr alles Lockere, wenn du fertig bist."],
    debrief=["NEXUS: 203.0.113.9. Dieselbe Adresse aus den Protokollen dieses Servers. Es beobachtet nicht mehr "
             "den Dead Drop. Es beobachtet dich.",
             "MIRA: Das ist nicht Reyes' Stil, und es ist nicht zufällig. Jemand, der geduldig genug ist, "
             "wochenlang zu warten, tut das nicht als Hobby.",
             "NEXUS: Kapitel abgeschlossen. Was immer das ist, es ist gerade persönlich geworden. Wir sollten "
             "herausfinden, wer tatsächlich dahintersteckt — vorsichtig."],
    objectives=[
        {"text": "Nachsehen, was läuft (ps aux)", "hints": ["ps aux listet jeden Prozess mit Besitzer und PID.", "Versuch: ps aux", "ps aux"]},
        {"text": "Den Relais-Prozess stoppen (kill 6650)", "hints": ["kill PID stoppt einen Prozess, sobald man seine Nummer kennt.", "Versuch: kill 6650", "kill 6650"]},
        {"text": "Die Login-Historie prüfen (last)", "hints": ["last zeigt eine Historie, wer sich eingeloggt hat, und von wo.", "Versuch: last", "last"]},
        {"text": "access.token sperren (chmod 600)", "hints": ["chmod 600 beschränkt eine Datei auf ihren Besitzer.", "Versuch: chmod 600 access.token", "chmod 600 access.token"]},
    ],
)

register(
    "act2_m31", "de",
    title="Eine Kopie behalten",
    briefing=["MIRA: Gleiche Übung wie vorher, aber diesmal brauche ich eine Kopie des Ergebnisses, nicht nur "
              "einen Blick darauf. tee lässt dich beides in einem Atemzug tun — sehen und speichern."],
    debrief=["MIRA: Danach wirst du ständig greifen. Etwas zu sehen und es zu behalten sind zwei verschiedene Probleme."],
    objectives=[
        {"text": "auth_events.log sortieren", "hints": ["Gleiches Muster wie vorher: erst sortieren, dann zählen.", "Versuch: sort auth_events.log", "sort auth_events.log"]},
        {"text": "Zählen und in einer Zeile eine Kopie speichern (uniq -c | tee)",
         "hints": ["tee schreibt in eine Datei UND zeigt dir weiterhin die Ausgabe.", "Versuch: sort auth_events.log | uniq -c | tee summary.txt",
                  "sort auth_events.log | uniq -c | tee summary.txt"]},
    ],
)

register(
    "act2_m32", "de",
    title="Diesmal speichern",
    briefing=["NEXUS: Bevor auf dieser Maschine noch irgendwas Seltsames passiert, will ich eine schriftliche "
              "Ausgangslage, was eigentlich laufen SOLLTE. Speichere sie — nicht nur anschauen und weitergehen."],
    debrief=["NEXUS: Abgelegt. Wenn das nächste Mal etwas komisch aussieht, haben wir etwas Ehrliches zum Vergleichen."],
    objectives=[{"text": "Eine Prozess-Ausgangslage schreiben und zurücklesen",
                "hints": ["> leitet die Ausgabe eines Befehls in eine Datei statt auf den Bildschirm.",
                         "Versuch: ps aux > process_report.txt, dann cat process_report.txt", "ps aux > process_report.txt\ncat process_report.txt"]}],
)

register(
    "act2_m33", "de",
    title="Das Rauschen umleiten",
    briefing=["MIRA: Lies siteA, siteB und siteC zusammen aus. Es gibt noch kein siteC, also leite alle Fehler, "
              "die das wirft, in eine eigene Datei um, statt die echte Ausgabe damit zuzumüllen."],
    debrief=["MIRA: Saubere Ausgabe, Fehler separat abgelegt. Das ist der Unterschied zwischen einem Bericht und "
             "einem Durcheinander."],
    objectives=[{"text": "Den Fehler der fehlenden Datei in errors.log umleiten und nachsehen",
                "hints": ["2> schickt nur Fehlermeldungen in eine Datei, die normale Ausgabe bleibt unberührt.",
                         "Versuch: cat siteA.cfg siteB.cfg siteC.cfg 2> errors.log, dann cat errors.log",
                         "cat siteA.cfg siteB.cfg siteC.cfg 2> errors.log\ncat errors.log"]}],
)

register(
    "act2_m34", "de",
    title="Hineinfüttern",
    briefing=["NEXUS: Mira will, dass diese Nachricht geschrien statt geflüstert wird — alles in Großbuchstaben, "
              "in einer neuen Datei gespeichert."],
    debrief=["NEXUS: tr nimmt nie direkt einen Dateinamen — < ist der einzig saubere Weg, ihm eine zu geben."],
    objectives=[{"text": "message.txt in Großbuchstaben nach shout.txt umwandeln und nachsehen",
                "hints": ["tr liest nur von der Standardeingabe, nie von einem Dateinamen — < füttert es mit einer Datei.",
                         "Versuch: tr a-z A-Z < message.txt > shout.txt, dann cat shout.txt", "tr a-z A-Z < message.txt > shout.txt\ncat shout.txt"]}],
)

register(
    "act2_m35", "de",
    title="Reyes' Angebot",
    briefing=["NEXUS: Reyes schon wieder. Diesmal will er tatsächlich etwas. Lies es."],
    debrief=["NEXUS: Was auch immer du ihnen gesagt hast, das steht jetzt zu Buche. Ich hoffe, es war die richtige Entscheidung.",
             "MIRA: Bei Reyes gibt's nicht immer eine saubere Antwort. Willkommen bei der Arbeit mit anderen Leuten."],
    objectives=[
        {"text": "Reyes' Angebot lesen", "hints": ["Schau in deinen Posteingang.", "Versuch: cat inbox/reyes_offer.txt", "cat inbox/reyes_offer.txt"]},
        {"text": "Antworten — deine Entscheidung, was du ihnen sagst",
         "hints": ["Gleiche Vorgehensweise wie bei Mira ganz am Anfang: schreiben, an die Datei anhängen.",
                  'echo "deine Antwort hier" >> inbox/reyes_offer.txt', 'echo "Abgemacht." >> inbox/reyes_offer.txt']},
    ],
)

register(
    "act2_m36", "de",
    title="Zahlen, alt und neu",
    briefing=["MIRA: Nummerier mir diese Liste, lesbar, zum Drucken. Und ich brauche zehn frische Fallnummern — "
              "101 bis 110 reicht."],
    debrief=["MIRA: Kleinkram, aber es ist der Kleinkram, der einen Bericht so aussehen lässt, als käme er von "
             "jemandem, der weiß, was er tut."],
    objectives=[
        {"text": "Die Liste nummerieren (nl)", "hints": ["nl nummeriert jede nicht-leere Zeile einer Datei.", "Versuch: nl contacts.roster", "nl contacts.roster"]},
        {"text": "Fallnummern 101-110 erzeugen (seq)", "hints": ["seq ERSTE LETZTE gibt eine Zahlenreihe aus.", "Versuch: seq 101 110", "seq 101 110"]},
    ],
)

register(
    "act2_m37", "de",
    title="Rückwärts lesen",
    briefing=["NEXUS: Diese Datei liest sich vorwärts als Unsinn. Reyes hat das schon mal gemacht — versuch's rückwärts."],
    debrief=["NEXUS: 'Sie sind näher, als du denkst.' Reyes' Vorstellung von einem Scherz, vermutlich. Vermutlich."],
    objectives=[{"text": "scrambled.txt rückwärts lesen (rev)",
                "hints": ["rev dreht jede Zeile um, Zeichen für Zeichen.", "Versuch: rev scrambled.txt", "rev scrambled.txt"]}],
)

register(
    "act2_m38", "de",
    title="Eine Tabelle, keine zwei Listen",
    briefing=["MIRA: Führ die nebeneinander zu einer Tabelle zusammen, sauber ausgerichtet. Ich lese nicht zwei "
              "getrennte Listen und gleiche sie selbst ab."],
    debrief=["MIRA: Das ist jetzt ein Bericht. Formatier Dinge weiter so, als würdest du erwarten, dass sie "
             "wirklich jemand liest."],
    objectives=[
        {"text": "Die beiden Dateien nebeneinanderlegen (paste)",
         "hints": ["paste fügt Dateien Zeile für Zeile nebeneinander zusammen.", "Versuch: paste names.txt statuses.txt", "paste names.txt statuses.txt"]},
        {"text": "Die Spalten ausrichten (column -t)",
         "hints": ["column -t macht aus trennzeichen-getrenntem Text eine ausgerichtete Tabelle.",
                  "Versuch: paste names.txt statuses.txt | column -t", "paste names.txt statuses.txt | column -t"]},
    ],
)

register(
    "act2_m39", "de",
    title="Großreinemachen",
    briefing=["NEXUS: Dieser Spool-Ordner von vorhin ist immer noch voller Testdateien, die niemand braucht. "
              "Finde sie alle und räum sie in einem Rutsch weg — nicht einzeln löschen."],
    debrief=["NEXUS: Vier Dateien, ein Befehl. Das ist der ganze Sinn von xargs."],
    objectives=[
        {"text": "Jede .tmp-Datei in einem Rutsch löschen (find | xargs rm)",
         "hints": ["find listet die Dateien; xargs macht aus dieser Liste Argumente für einen anderen Befehl.",
                  "Versuch: find .cache/spool -name '*.tmp' | xargs rm", "find .cache/spool -name '*.tmp' | xargs rm"]},
        {"text": "Alle vier Testdateien wirklich weg",
         "hints": ["Wenn xargs den Befehl richtig gebaut hat, sollten alle vier auf einen Schlag verschwinden.",
                  "find .cache/spool -name '*.tmp' | xargs rm", "find .cache/spool -name '*.tmp' | xargs rm"]},
    ],
)

register(
    "act2_m40", "de",
    title="Kompletter Durchlauf",
    briefing=["MIRA: Voller Durchlauf, bevor wir dieses Kapitel für beendet erklären: zieh jede ERROR-Zeile aus "
              "den Protokollen dieser Woche — es ist eine dritte Datei aufgelistet, die nicht existiert, lass die "
              "nicht die echte Ausgabe kaputt machen — speicher eine Kopie von dem, was du findest, sieh dir "
              "separat an, welche Fehler das wirft, und räum danach die Testdateien weg."],
    debrief=["MIRA: Zwei echte Fehler, ein toter Dateiverweis, und ein aufgeräumter Arbeitsbereich am Ende. Das "
             "ist der ganze Job, jedes Mal, nur in unterschiedlichem Maßstab.",
             "NEXUS: Kapitel abgeschlossen. Was auch immer als Nächstes kommt, du hast jetzt die Gewohnheiten dafür."],
    objectives=[
        {"text": "ERROR-Zeilen aus allen Protokollen auf einmal ziehen (grep -h)",
         "hints": ["-h verhindert, dass mehrere Dateien die Ausgabe mit Dateinamen zumüllen.",
                  "Versuch: grep -h ERROR logs/w1.log logs/w2.log logs/w3.log 2> scan_errors.log | tee scan_results.txt"]},
        {"text": "Die gespeicherten Ergebnisse prüfen (scan_results.txt)",
         "hints": ["tee hat eine Kopie geschrieben, während du zugesehen hast — lies sie zurück.", "Versuch: cat scan_results.txt", "cat scan_results.txt"]},
        {"text": "Separat prüfen, was schiefging (scan_errors.log)",
         "hints": ["2> hat den Fehler der fehlenden Datei in eine eigene Datei umgeleitet.", "Versuch: cat scan_errors.log", "cat scan_errors.log"]},
        {"text": "Die Testdateien wegräumen (find | xargs rm)",
         "hints": ["Gleicher Handgriff wie beim Spool-Aufräumen.", "Versuch: find . -name '*.tmp' | xargs rm", "find . -name '*.tmp' | xargs rm"]},
    ],
)

register(
    "act2_m41", "de",
    title="Was Reyes gefunden hat",
    briefing=["NEXUS: Reyes hat tatsächlich geliefert. Es gibt einen Dossier-Ordner — durchsuch alles auf einmal, "
              "nicht Datei für Datei."],
    debrief=["NEXUS: Nicht extern, nicht zufällig, und mehr als einmal markiert. Reyes hat nicht übertrieben.",
             "MIRA: Mehr, als ich erwartet hätte, dass sie tatsächlich rausrücken."],
    objectives=[
        {"text": "Reyes' Nachtrag lesen", "hints": ["Schau zuerst in deinen Posteingang.", "Versuch: cat inbox/reyes_followup.txt", "cat inbox/reyes_followup.txt"]},
        {"text": "Den ganzen Dossier auf einmal nach 203.0.113.9 durchsuchen (grep -r)",
         "hints": ["-r lässt grep jede Datei unter einem Ordner durchsuchen, nicht nur eine.", "Versuch: grep -r 203.0.113.9 dossier", "grep -r 203.0.113.9 dossier"]},
    ],
)

register(
    "act2_m42", "de",
    title="Wie oft",
    briefing=["MIRA: Sag mir nicht nur, wo es auftaucht. Sag mir, wie oft, insgesamt, über alles hinweg."],
    debrief=["MIRA: Vier. Verteilt, geduldig, nie in Eile. Passt zu allem, was wir sonst gesehen haben."],
    objectives=[{"text": "Jede Erwähnung im ganzen Dossier zählen",
                "hints": ["Leite das rekursive grep in wc -l, um die Treffer zu summieren.",
                         "Versuch: grep -r 203.0.113.9 dossier | wc -l", "grep -r 203.0.113.9 dossier | wc -l"]}],
)

register(
    "act2_m43", "de",
    title="Eine klare Antwort",
    briefing=["NEXUS: Mira will eine klare Antwort. Lies es, dann gib ihr eine."],
    debrief=["MIRA: Notiert. Was auch immer als Nächstes passiert, das ist die Linie, die DU gezogen hast, nicht ich.",
             "NEXUS: Für das, was es wert ist — ich hätte genauso geantwortet. Zitier mich nicht damit, dass ich 'Wert' hätte."],
    objectives=[
        {"text": "Miras Nachfrage lesen", "hints": ["Schau in deinen Posteingang.", "Versuch: cat inbox/mira_checkin.txt", "cat inbox/mira_checkin.txt"]},
        {"text": "Ihr eine klare Antwort geben",
         "hints": ["Gleiche Vorgehensweise wie zuvor — schreiben, an die Datei anhängen.",
                  'echo "deine Antwort hier" >> inbox/mira_checkin.txt', 'echo "Ich bin dabei. Ganz." >> inbox/mira_checkin.txt']},
    ],
)

register(
    "act2_m44", "de",
    title="Den ganzen Ordner zusperren",
    briefing=["NEXUS: Wenn wir das weitertreiben, muss der ganze Dossier-Ordner zuerst gesperrt werden. Alles "
              "davon, nicht Datei für Datei. Nimm 700, nicht 600 — ein Ordner braucht sein eigenes Ausführungsrecht, "
              "nur um betreten zu werden, selbst vom Besitzer. Entfernst du das, sperrst du dich selbst aus, "
              "zusammen mit allen anderen."],
    debrief=["NEXUS: Gut. Was auch immer als Nächstes passiert, dieser Ordner ist nicht die Schwachstelle."],
    objectives=[{"text": "Den ganzen Dossier-Ordner sperren (chmod -R 700)",
                "hints": ["-R wendet chmod auf einen Ordner und alles darin an. Nimm 700, nicht 600 — Verzeichnisse "
                         "brauchen ihr eigenes Ausführungsrecht, um betreten zu werden, selbst vom Besitzer.",
                         "Versuch: chmod -R 700 dossier", "chmod -R 700 dossier"]}],
)

register(
    "act2_m45", "de",
    title="Fall vorerst geschlossen",
    briefing=["MIRA: Zieh alles über 203.0.113.9 in eine Datei, behalte eine Kopie, die nur root anfassen kann, "
              "und wir sind fertig mit diesem Kapitel."],
    debrief=["MIRA: Abgelegt, gesperrt und gesichert. Das ist alles, was wir von außen lernen können.",
             "NEXUS: Wer auch immer hinter dieser Adresse steckt, wird nicht freiwillig mehr preisgeben als das. "
             "Das heißt, der nächste Schritt geht direkt auf die Quelle zu — ihre eigene Infrastruktur, nicht nur "
             "ihr Schatten in einer Protokolldatei.",
             "MIRA: Rangaufstieg. NETRUNNER. Du hast es dir verdient, und du wirst es brauchen — ab hier hören "
             "Fußspuren auf, es zu sein, und es wird das eigentliche Gebäude."],
    objectives=[
        {"text": "Die Fallakte zusammenstellen und prüfen (grep -r ... | tee)",
         "hints": ["Gleicher Trick wie vorher — suchen, und eine Kopie speichern, während du hinschaust.",
                  "Versuch: grep -r 203.0.113.9 dossier | tee case_summary.txt", "grep -r 203.0.113.9 dossier | tee case_summary.txt\ncat case_summary.txt"]},
        {"text": "Eine Kopie dort sichern, wo nur root hinkommt (sudo cp)",
         "hints": ["Der Archiv-Ordner gehört nur root — du brauchst sudo, um dort etwas abzulegen. Er liegt unter "
                  "/archive, nicht in deinem Home-Ordner.",
                  "Versuch: sudo cp case_summary.txt /archive/case_summary.txt", "sudo cp case_summary.txt /archive/case_summary.txt"]},
    ],
)
