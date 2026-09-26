.include "macro.inc"

.section .text, "ax"

glabel gspL3DEX_fifoTextStart
.incbin "bin/core1/gSPL3DEX_fifo.textbin.bin"
endlabel gspL3DEX_fifoTextStart
glabel gspL3DEX_fifoTextEnd

.section .rodata, "a"

glabel gspL3DEX_fifoDataStart
.incbin "bin/core1/gSPL3DEX_fifo.rodatabin.bin"
glabel gspL3DEX_fifoDataEnd
