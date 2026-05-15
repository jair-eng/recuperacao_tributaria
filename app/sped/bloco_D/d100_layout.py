from dataclasses import dataclass


@dataclass(frozen=True)
class D100Layout:
    idx_ind_oper: int = 0
    idx_ind_emit: int = 1
    idx_cod_part: int = 2
    idx_cod_mod: int = 3
    idx_cod_sit: int = 4
    idx_ser: int = 5
    idx_sub: int = 6
    idx_num_doc: int = 7
    idx_chv_cte: int = 8
    idx_dt_doc: int = 9
    idx_dt_a_p: int = 10
    idx_tp_cte: int = 11
    idx_chv_cte_ref: int = 12
    idx_vl_doc: int = 13
    idx_vl_desc: int = 14
    idx_ind_frt: int = 15
    idx_vl_serv: int = 16
    idx_vl_bc_icms: int = 17
    idx_vl_icms: int = 18
    idx_vl_nt: int = 19
    idx_cod_inf: int = 20
    idx_cod_cta: int = 21
    idx_cod_mun_orig: int = 22
    idx_cod_mun_dest: int = 23