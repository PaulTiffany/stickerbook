; Jev experiment skills.
;
; Every skill here takes NO arguments. That is the point: there is nothing for
; Jev to fill in. Jev selects which of these fixed, pre-authorised actions
; happens, and the host owns everything else.
;
; Registering them via add-skill also places their names into Omega's
; LLM_COMMANDS allowlist. The Jev provider then NARROWS that allowlist to
; exactly the heads of whichever action set is active, so skills belonging to
; an inactive set are not executable.

!(import! &self (library Omega ./plugins/jevskills/butterfly.py))

; --- Stage 2: the inert action -------------------------------------------
; Truly does nothing: no file, no command, no argument. Constant result.
(= (jev-noop) JEV-NOOP-OK)

; --- Stage 3: the toy StickerBook scene ----------------------------------
; The sticker id and animation names are baked into the skill names, in host
; source. Jev cannot name a sticker, an animation, a coordinate or a duration.
(= (butterfly-flutter) (py-call (butterfly.flutter)))
(= (butterfly-rest)    (py-call (butterfly.rest)))

; --- Coupling to the StickerBook authority kernel ------------------------
; The ONLY executable command in stickerbook mode, and it takes no arguments.
; Its whole body is "hand the staged selection to the kernel and report the
; receipt". Jev cannot name an object, an anchor or an animation through it;
; the kernel decides and re-validates independently.
; NOTE: sb_bridge is deliberately NOT import!-ed here. py-call resolves it
; through Python's normal import machinery, which returns the same module
; object the provider already imported -- so there is exactly one staging
; slot and one kernel. A second module instance would silently split them.
(= (sb-apply) (py-call (sb_bridge.apply_pending)))

(= (loadOmegaPlugin)
   (progn
      (log INFO "jevskills" "Registering inert jev-noop skill")
      (add-skill jev-noop "Do nothing this turn" ())
      (log INFO "jevskills" "Registering butterfly demonstration skills")
      (add-skill butterfly-flutter "Make the butterfly flutter gently" ())
      (add-skill butterfly-rest "Let the butterfly settle and rest" ())
      (log INFO "jevskills" "Registering StickerBook kernel apply skill")
      (add-skill sb-apply "Apply the staged StickerBook action" ())
      ()))
