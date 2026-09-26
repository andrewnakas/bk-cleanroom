.include "macro.inc"

.section .text, "ax"

glabel gspF3DEX_fifoTextStart
.incbin "bin/core1/gSPF3DEX_fifo.textbin.bin"
endlabel gspF3DEX_fifoTextStart
glabel gspF3DEX_fifoTextEnd

.section .rodata, "a"

glabel gspF3DEX_fifoDataStart
.incbin "bin/core1/gSPF3DEX_fifo.rodatabin.bin"
glabel gspF3DEX_fifoDataEnd
