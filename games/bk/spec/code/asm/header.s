.section .data

.word 0x80371240       /* PI BSB Domain 1 register */
.word 0x0000000F       /* Clockrate setting */
.word 0x80100400       /* Entrypoint address */
.word 0x00001448       /* Revision */
.word 0xCD7559AC       /* Checksum 1 */
.word 0xB26CF5AE       /* Checksum 2 */
.word 0x00000000       /* Unknown 1 */
.word 0x00000000       /* Unknown 2 */
.ascii "Banjo-Kazooie       " /* Internal name */
.word 0x00000000       /* Unknown 3 */
.word 0x0000004E       /* Cartridge */
.ascii "BK"            /* Cartridge ID */
.ascii "E"             /* Country code */
.byte 0x01             /* Version */
