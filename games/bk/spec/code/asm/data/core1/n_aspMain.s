.include "macro.inc"

.section .text, "ax"

glabel n_aspMainTextStart
.incbin "bin/core1/n_aspMain.textbin.bin"
endlabel n_aspMainTextStart
glabel n_aspMainTextEnd

.section .rodata, "a"

glabel n_aspMainDataStart
.incbin "bin/core1/n_aspMain.rodatabin.bin"
glabel n_aspMainDataEnd
