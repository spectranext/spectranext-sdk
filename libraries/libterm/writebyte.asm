; int writebyte(int handle, int c)
; __smallc: left-to-right, so stack has ret, handle, c. Stdout (handle==1) goes to Spectranext terminal decode (BC=$043B).
    PUBLIC _writebyte
    PUBLIC writebyte

; Caller cleans stack: we pop ret, handle, c; do work; push back so caller can pop args; ret.
_writebyte:
writebyte:
    POP  BC          ; return address
    POP  DE          ; handle (first arg)
    POP  HL          ; c (second arg)
    PUSH HL
    PUSH DE
    PUSH BC          ; restore for return

    ; Stdout fd is 1. Check DE == 1 (D=0, E=1)
    LD   A, D
    OR   A
    JR   NZ, err
    LD   A, E
    CP   1
    JR   NZ, err

    ; Handle 1: output L to port $043B (Spectranext term stdout decode)
    LD   A, L
    LD   BC, $043B
    OUT  (C), A
    LD   HL, 1       ; return 1 (one byte written)
    RET

err:
    LD   HL, -1
    RET
