; Fixed StickerBook RPC return skill.
;
; Both OmegaLLM and OmegaJev service modes execute exactly this zero-argument
; command after staging a bounded JSON response in the host-facing channel.
; It does not touch the StickerBook authority kernel.
(= (sb-return) (py-call (stickerbookrpc.complete_staged)))

(= (loadOmegaPlugin)
   (progn
      (add-skill sb-return "Return the staged bounded result to StickerBook" ())
      ()))
