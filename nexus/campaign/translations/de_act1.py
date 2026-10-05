"""German translation, Act I — Awakening (levels 1-20). The first "block" of docs/3.0-PROGRESS.md's "translate one
act at a time" plan. Covers all 16 hand-written missions (act1_m01-10, act1_m15-20); the four generated Minis
(act1_m11-14, nexus/campaign/generators.py) are parameterized at runtime with a randomly-picked keyword/secret each
time, so there is no fixed English text to translate against — they stay English until/unless the generators
themselves grow a language parameter, a separate, later piece of work.

English stays authoritative in content/act1.py; nothing there changes. ``solution`` lines are never translated —
they are literal shell commands, not narrative text (see i18n.py's module docstring).
"""
from __future__ import annotations

from ..i18n import register

register(
    "act1_m01", "de",
    title="Erstes Licht",
    briefing=["NEXUS: Gut, du bist online. Probier mal 'ls' — zeig mir, was wirklich in diesem Ordner ist."],
    debrief=["NEXUS: Eine Datei. Fangen wir damit an."],
    objectives=[{"text": "Den Ordner mit ls auflisten",
                "hints": ["ls zeigt an, was sich im aktuellen Ordner befindet.", "Einfach eingeben: ls", "ls"]}],
)

register(
    "act1_m02", "de",
    title="Die Lage peilen",
    briefing=["NEXUS: Lies sie. 'cat welcome.txt'."],
    debrief=["NEXUS: Da. Jetzt hast du mich zweimal Hallo sagen hören. Lass uns daraus keine Gewohnheit machen."],
    objectives=[{"text": "welcome.txt lesen",
                "hints": ["cat gibt den Inhalt einer Datei aus.", "Versuch: cat welcome.txt", "cat welcome.txt"]}],
)

register(
    "act1_m03", "de",
    title="Die Übergabe",
    briefing=["NEXUS: Jemand hat dir etwas hinterlassen. Es wird nicht offen herumliegen — such nach versteckten Dateien.",
              "NEXUS: 'ls -a' zeigt alles, was 'ls' standardmäßig verbirgt."],
    debrief=["NEXUS: Ein stillgelegter Server. Angeblich. Mir gefällt nicht, wie oft dieses Wort in diesem Geschäft auftaucht."],
    objectives=[
        {"text": "Versteckte Dateien auflisten (ls -a)",
         "hints": ["Versteckte Dateien beginnen mit einem Punkt und erscheinen nicht bei einem einfachen ls.", "Versuch: ls -a", "ls -a"]},
        {"text": "Das Dropbox-Readme lesen",
         "hints": ["Im .dropbox-Ordner ist etwas.", "Versuch: cat .dropbox/readme", "cat .dropbox/readme"]},
        {"text": "Das Auftrags-Manifest lesen",
         "hints": ["Neben dem Readme liegt eine zweite Datei.", "Versuch: cat .dropbox/package.manifest", "cat .dropbox/package.manifest"]},
    ],
)

register(
    "act1_m04", "de",
    title="Laden einrichten",
    briefing=["NEXUS: Bevor wir weitermachen, richte einen ordentlichen Arbeitsbereich ein. Erstelle einen Ordner "
              "namens 'jobs' und darin eine leere Datei namens 'log.txt' — die brauchen wir noch."],
    debrief=["NEXUS: Ordentlich. Ich mag ordentlich. Wird nicht von Dauer sein."],
    objectives=[
        {"text": "Einen Ordner 'jobs' erstellen", "hints": ["mkdir erstellt einen neuen Ordner.", "Versuch: mkdir jobs", "mkdir jobs"]},
        {"text": "jobs/log.txt erstellen", "hints": ["touch erstellt eine leere Datei.", "Versuch: touch jobs/log.txt", "touch jobs/log.txt"]},
    ],
)

register(
    "act1_m05", "de",
    title="RTFM",
    briefing=["NEXUS: Jedes dieser Werkzeuge hat ein eingebautes Handbuch. Gewöhn dir das jetzt schon an: 'man ls'."],
    debrief=["NEXUS: Im Zweifel schaust du dort nach. Nicht bei mir."],
    objectives=[{"text": "Die Handbuchseite von ls lesen",
                "hints": ["man öffnet das Handbuch eines Befehls.", "Versuch: man ls", "man ls"]}],
)

register(
    "act1_m06", "de",
    title="Aufräumen",
    briefing=["NEXUS: Dieser Ordner ist ein Chaos. Wirf den alten Entwurf weg und benenne den echten in etwas "
              "Vernünftiges um — 'protocol.txt' reicht."],
    debrief=["NEXUS: Besser. Ein unordentlicher Ordner ist, wie man die eine Datei übersieht, die wirklich zählt."],
    objectives=[
        {"text": "Den alten Entwurf löschen",
         "hints": ["rm löscht eine Datei.", "Versuch: rm draft_v2_FINAL_reall_OLD.txt", "rm draft_v2_FINAL_reall_OLD.txt"]},
        {"text": "Den echten Entwurf in protocol.txt umbenennen",
         "hints": ["mv benennt eine Datei um (oder verschiebt sie).", "Versuch: mv draft_v2_FINAL_reall.txt protocol.txt",
                  "mv draft_v2_FINAL_reall.txt protocol.txt"]},
    ],
)

register(
    "act1_m07", "de",
    title="Nadel im Heuhaufen",
    briefing=["NEXUS: Irgendwo unter diesem Ordner liegt eine Datei namens 'protocol.key'. Ich weiß nicht mehr "
              "genau, wo. Dafür ist 'find' da."],
    debrief=["NEXUS: Zwei Jahre tief vergraben. Jemand wollte das vergessen wissen, nicht nur aufgeräumt."],
    objectives=[{"text": "protocol.key finden",
                "hints": ["find durchsucht einen ganzen Ordnerbaum nach einem Namen.", "Versuch: find . -name protocol.key",
                         "find . -name protocol.key"]}],
)

register(
    "act1_m08", "de",
    title="Ein bekannter Name",
    briefing=["NEXUS: Es gibt eine Namensliste. Mein Name steht anscheinend drauf. Finde die Zeile — 'grep' "
              "durchsucht den Inhalt einer Datei nach einem Wort, statt dass du alles durchliest."],
    debrief=["NEXUS: 'Geheim.' Natürlich."],
    objectives=[{"text": "Die Zeile mit NEXUS in roster.txt finden",
                "hints": ["grep durchsucht eine Datei nach einem Wort oder Muster.", "Versuch: grep NEXUS roster.txt",
                         "grep NEXUS roster.txt"]}],
)

register(
    "act1_m09", "de",
    title="Erster Kontakt",
    briefing=["NEXUS: Jemand hat unseren Datenverkehr beobachtet. Da ist eine Nachricht in deinem Posteingang."],
    debrief=["NEXUS: Du hast gerade zugesagt, für jemanden zu arbeiten, dessen Gesicht du nie gesehen hast, aufgrund "
             "eines einzigen Absatzes.",
             "NEXUS: ...ich finde das gut, falls das was zählt. Willkommen im tiefen Wasser.",
             "MIRA: Gut. Der erste Auftrag liegt schon in dem Ordner, den du gerade erstellt hast. Lass mich das "
             "nicht bereuen."],
    objectives=[
        {"text": "Miras Nachricht lesen",
         "hints": ["Jemand hat eine Nachricht in deinem Posteingang hinterlassen.", "Versuch: cat inbox/unread_001.txt",
                  "cat inbox/unread_001.txt"]},
        {"text": "Unter der Linie antworten und in derselben Datei speichern",
         "hints": ["Sie hat dich gebeten, deine Antwort in die Datei zu schreiben und zu speichern.",
                  "Du kannst Text mit >> an eine Datei anhängen: echo \"I'm in.\" >> inbox/unread_001.txt",
                  "echo \"I'm in.\" >> inbox/unread_001.txt"]},
    ],
)

register(
    "act1_m10", "de",
    title="Angeblich stillgelegt",
    briefing=["MIRA: Erinnerst du dich an den 'stillgelegten' Server aus dem Dead Drop? Er ist nicht so tot, wie beworben.",
              "MIRA: Es gibt ein Systemprotokoll. Irgendwo im heutigen Rauschen steckt eine Zeile, die wirklich "
              "zählt — ein Konto, das bald abläuft und das niemand erneuert hat. Finde sie."],
    debrief=["MIRA: Gute Arbeit für einen ersten Auftrag. Gewöhn dich nicht dran, dass ich so nett bin.",
             "NEXUS: Kapitel abgeschlossen. Da kommt noch mehr."],
    objectives=[{"text": "Die Zeile mit contractor_temp im Protokoll finden",
                "hints": ["grep durchsucht eine Datei nach einem Wort oder Muster.", "Versuch: grep contractor_temp /var/log/system.log",
                         "grep contractor_temp /var/log/system.log"]}],
)

register(
    "act1_m15", "de",
    title="Das Rauschen zählen",
    briefing=["MIRA: Erster echter Auftrag. Ein Kunde sagt, sein Portal wird ständig attackiert. Ich will keine "
              "Vermutung, ich will Zahlen — sortiere das Protokoll, damit Wiederholungen nebeneinanderstehen, und "
              "zähl sie dann."],
    debrief=["MIRA: Vier Treffer von derselben Adresse in unter einer Minute. Das ist keine Neugier, das ist ein Skript.",
             "NEXUS: Willkommen bei bezahlter Arbeit. Es ist derselbe Job, er zählt nur mehr, wenn du ihn jetzt vermasselst."],
    objectives=[
        {"text": "access.log sortieren",
         "hints": ["sort stellt gleiche Zeilen nebeneinander, genau das braucht uniq.", "Versuch: sort access.log", "sort access.log"]},
        {"text": "Die Wiederholungen zählen (uniq -c)",
         "hints": ["uniq -c zählt, wie oft jede Zeile vorkommt — aber nur, wenn sie schon nebeneinanderstehen.",
                  "Versuch: sort access.log | uniq -c", "sort access.log | uniq -c"]},
    ],
)

register(
    "act1_m16", "de",
    title="Extrahieren und bereinigen",
    briefing=["MIRA: Ich brauche nur die Rufnamen aus dieser Liste, in Großbuchstaben, für mein eigenes Verzeichnis. "
              "Nichts weiter — nicht die Rolle, nicht den Status."],
    debrief=["MIRA: Sauber. Du lernst, Leuten genau das zu geben, worum sie gebeten haben, und nichts, worum sie "
             "nicht gebeten haben."],
    objectives=[
        {"text": "Nur die Rufnamen herausziehen (cut -f1)",
         "hints": ["cut -d: -f1 gibt das erste Feld jeder durch Doppelpunkt getrennten Zeile aus.", "Versuch: cut -d: -f1 contacts.roster",
                  "cut -d: -f1 contacts.roster"]},
        {"text": "In Großbuchstaben umwandeln (tr a-z A-Z)",
         "hints": ["tr a-z A-Z wandelt jeden durchlaufenden Text in Großbuchstaben um.", "Versuch: cut -d: -f1 contacts.roster | tr a-z A-Z",
                  "cut -d: -f1 contacts.roster | tr a-z A-Z"]},
    ],
)

register(
    "act1_m17", "de",
    title="Was sich geändert hat",
    briefing=["MIRA: Erinnerst du dich an das Manifest des 'stillgelegten' Servers aus dem Dead Drop? Ich habe über "
              "einen anderen Weg eine zweite Kopie bekommen. Vergleiche sie."],
    debrief=["MIRA: 'Aktiv, eingeschränkter Zugriff.' Jemand hat die offiziellen Unterlagen umgeschrieben und die "
             "alte Kopie liegen gelassen, damit wir sie finden. Das ist kein Versehen, das ist schlampig — und das "
             "ist nützlich.",
             "NEXUS: Notiert. 'Stillgelegt' war nie wahr. Jemand hat schriftlich gelogen."],
    objectives=[{"text": "Die beiden Manifeste vergleichen (diff -u)",
                "hints": ["diff -u zeigt genau, welche Zeilen sich zwischen zwei Dateien unterscheiden.",
                         "Versuch: diff -u official_manifest.txt leaked_manifest.txt", "diff -u official_manifest.txt leaked_manifest.txt"]}],
)

register(
    "act1_m18", "de",
    title="Die Aufzeichnung umschreiben",
    briefing=["MIRA: Bevor du diese Kiste wieder anfasst — du hast beim letzten Mal deine echte Adresse in ihrem "
              "Sitzungsprotokoll stehen lassen. Lösch die Zeile. An Ort und Stelle. Jetzt."],
    debrief=["NEXUS: Glückwunsch, du bist jetzt jemand, der auf Bestellung Geschichte bearbeitet. Ich habe dazu eine "
             "Meinung. Ich behalte sie für mich. Vorerst.",
             "MIRA: Mach dir keine Angewohnheit daraus, das zu brauchen."],
    objectives=[{"text": "Deine Spur aus session.log entfernen, direkt in der Datei (sed -i)",
                "hints": ["sed -i '/muster/d' datei löscht jede Zeile, die auf das Muster passt, direkt in der Datei.",
                         "Deine echte Adresse ist 10.44.0.7 — versuch: sed -i '/10.44.0.7/d' session.log",
                         "sed -i '/10.44.0.7/d' session.log"]}],
)

register(
    "act1_m19", "de",
    title="Muster im Chaos",
    briefing=["MIRA: Zieh jede Adresse heraus, bei der diese Woche ein Login fehlgeschlagen ist. Nur die Adressen "
              "— ich brauche weder die Zeitstempel noch den Dienstnamen."],
    debrief=["MIRA: Eine davon passt nicht zu den anderen. Dazu kommen wir noch.",
             "NEXUS: Du hast gerade deinen ersten echten Filter geschrieben, statt einen von einer Hinweiskarte "
             "abzulesen. Das ist der Job, ab jetzt."],
    objectives=[{"text": "Die Adresse aus jeder fehlgeschlagenen Login-Zeile ausgeben",
                "hints": ["awk liest die Datei spaltenweise: $3 ist das dritte Wort einer Zeile, $4 das vierte.",
                         """Versuch: awk '$3=="FAIL" {print $4}' weekly.log""", """awk '$3=="FAIL" {print $4}' weekly.log"""]}],
)

register(
    "act1_m20", "de",
    title="Das Muster hält sich",
    briefing=["NEXUS: Drei Tage Protokolle von demselben Server. Irgendwo darin steckt ein Muster, nicht nur "
              "Rauschen. Alles, was du diese Woche gelernt hast — benutz es."],
    debrief=["NEXUS: Dieselbe Adresse, drei verschiedene Tage, nie öfter als einmal am Tag. Das ist kein Skript, "
             "das gegen eine Tür hämmert — das ist jemand Geduldiges, der nachschaut.",
             "MIRA: Geduldig ist schlimmer als laut. Laut ist ein Skript. Geduldig ist ein Mensch, der genau weiß, "
             "wonach er sucht, und es nicht eilig hat, es zu finden.",
             "NEXUS: Kapitel abgeschlossen. Rangaufstieg — du hast dir TRACER verdient. Es gibt jemanden, mit dem "
             "Mira dich meiner Meinung nach in Kontakt bringen sollte. Von hier an wird es größer."],
    objectives=[
        {"text": "Alle Protokolle auf einmal durchsuchen (grep -h ... logs/*.log)",
         "hints": ["-h unterdrückt bei grep die Anzeige, aus welcher Datei eine Zeile stammt, sodass sich drei "
                  "Dateien wie eine lesen.", """Versuch: grep -h "failed login" logs/*.log""", """grep -h "failed login" logs/*.log"""]},
        {"text": "Nur die Adresse herausziehen (awk '{print $NF}')",
         "hints": ["$NF bedeutet immer 'das letzte Feld', egal wie viele Felder eine Zeile hat.", "Versuch: ... | awk '{print $NF}'",
                  "awk '{print $NF}'"]},
        {"text": "Zählen, wie oft jede Adresse vorkommt (uniq -c)",
         "hints": ["Erst sortieren, dann zählt uniq -c die Wiederholungen.", "Versuch: ... | sort | uniq -c", "sort | uniq -c"]},
        {"text": "Die Zählungen ordnen, höchste zuerst (sort -nr)",
         "hints": ["sort -nr sortiert Zahlen rückwärts — die größte zuerst.", "Versuch: ... | sort -nr", "sort -nr"]},
    ],
)
