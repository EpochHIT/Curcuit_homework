'''
@brief 这个文件定义了拓扑结构的电气化实现
'''
import math
import cmath
try:
    from Core.topology import Node, Branch, Component
except ModuleNotFoundError:
    from topology import Node, Branch, Component
import numpy as np # type: ignore

def intelligent_output(value, unit_table : list[str], unit_k) -> tuple[float, str]:
    '''
    @brief 智能输出函数，可以自动选择合适的单位输出
    @detail 根据单位表自动转换单位
    @param value 基础单位（字典中系数为 1 的单位）下的数值
    @param unit_table 单位名称表，从小到大排列
    @param unit_k 单位表中单位的系数
    @return 转换后的数值和单位
    '''
    for i in range(len(unit_table)):
        if unit_k[i] == 1:
            break
    v = value
    if abs(v) < 1:
        while i > 0:
            i -= 1
            v = unit_k[i] * value
            if abs(v) >= 1:
                break
    else:
        while i < len(unit_table) - 1:
            i += 1
            v = value * unit_k[i]
            if abs(v) < 1:
                i -= 1
                v = value * unit_k[i]
                break
    return v, unit_table[i]

def get_vp(num : complex):
    """
    @brief 获取复数的幅值和相位
    @param num 复数
    @return 幅值和相位
    """
    if not isinstance(num, complex):
        num = complex(num)
    value = abs(num)
    phase = math.degrees(math.atan2(num.imag, num.real))
    if phase == 180 or phase == -180:
        phase = 0
        value = -value
    return value, phase


# 电压单位表
V_table = ['mV', 'V', 'kV', 'MV']
V_k = [1e3, 1, 1e-3, 1e-6]
# 电流单位表
I_table = ['μA', 'mA', 'A', 'kA']
I_k = [1e6, 1e3, 1, 1e-3]
# 电阻/阻抗单位表
R_table = ['mΩ', 'Ω', 'kΩ', 'MΩ']
R_k = [1e3, 1, 1e-3, 1e-6]
# 电容单位表
C_table = ['pF', 'nF', 'μF', 'mF', 'F']
C_k = [1e12, 1e9, 1e6, 1e3, 1]
# 电感单位表
L_table = ['μH', 'mH', 'H']
L_k = [1e6, 1e3, 1]
# 频率单位表
F_table = ['Hz', 'kHz', 'MHz', 'GHz']
F_k = [1, 1e-3, 1e-6, 1e-9]

FREQ = None     # 频率
OMEGA = None    # 角频率

def set_freq(freq : float):
    '''
    @brief 设置频率
    @param freq 频率，单位为 Hz
    '''
    global FREQ, OMEGA
    FREQ = freq
    OMEGA = 2 * math.pi * FREQ
set_freq(1000)    # 默认频率为 1kHz

class ElectricalNode(Node):
    """
    电气节点类，继承自基础节点类。
    增加了电气属性（电压、连接支路）。
    支持多支路并联。
    """
    def __init__(self, num: int):
        super().__init__(num)
        self._V = None

    def _get_V(self):
        return self._V
    def _set_V(self, V):
        self._V = V
    V = property(_get_V, _set_V)    # 电压

    def __str__(self):
        if self.V is not None:
            v, p = get_vp(self.V)
            v, unit = intelligent_output(v, V_table, V_k)
            return f"Node{self.num} V={v:.2f}∠{p:.2f}° {unit}"
        else:
            return f"Node{self.num}"

class ElectricalBranch(Branch):
    """
    电气支路类，继承自基础支路类。
    增加了电气属性，支持多元件串联。
    """
    def __init__(self, node1: ElectricalNode, node2: ElectricalNode):
        super().__init__(node1, node2)
        self._I = None
        self._V1 = None
        self._V2 = None

    def _get_Z(self):
        # 计算支路总阻抗（所有元件串联）
        z = 0
        for c in self:
            if hasattr(c, 'Z') and c.Z is not None:
                z += c.Z
        return z
    Z = property(_get_Z)

    def _get_Y(self):
        # 计算支路总导纳
        z = self.Z
        if z == 0:
            return complex(0, 0)
        return 1 / z
    Y = property(_get_Y)    # 支路总导纳，只读

    def _get_I(self):
        return self._I
    def _set_I(self, I):
        self._I = I
    I = property(_get_I, _set_I)    # 电流

    def _get_V1(self):
        return self._V1
    def _set_V1(self, V):
        self._V1 = V
    V1 = property(_get_V1, _set_V1)    # 节点1电势

    def _get_V2(self):
        return self._V2
    def _set_V2(self, V):
        self._V2 = V
    V2 = property(_get_V2, _set_V2)    # 节点2电势

    def __str__(self):
        if self.I is not None:
            v, p = get_vp(self.I)
            i, unit = intelligent_output(v, I_table, I_k)
            return f"Branch({self.node_left} --- {self.node_right}) I={i:.2f}∠{p:.2f}° {unit}"
        else:
            return f"Branch({self.node_left} --- {self.node_right})"

COMPONENT_DICT = {}

class ElectricalComponent(Component):
    '''
    @brief 电气二端元件类
    @detail 继承自二端元件类，增加了电气属性，所有电气属性为None表示未知
    '''

    COUNTTABLE = {}    # 二端元件计数表

    def __init__(self, branch : ElectricalBranch, prefix : str = "Component"):
        '''
        @brief 电气二端元件类的构造函数
        @param branch 所在支路
        @param prefix 二端元件的前缀，会根据前缀自动分配编号，为None表示不需要编号
        '''
        super().__init__(branch)
        self._I = None
        self._U = None
        self._V1 = None
        self._V2 = None
        self.Vref = True    # 电压参考方向，True表示左端为正，False表示右端为正
        self.Iref = True    # 电流参考方向，True表示从左端流入，False表示从右端流入

        if prefix is None:
            return
        self.prefix = prefix
        self.num = self.COUNTTABLE.get(prefix, 0) + 1    # 二端元件编号
        self.COUNTTABLE[prefix] = self.num
        COMPONENT_DICT[f"{prefix}{self.num}"] = self

    def _get_I(self):
        return self._I
    def _set_I(self, I):
        self._I = I
    I = property(_get_I, _set_I)    # 电流

    def _get_U(self):
        if self._U is None:
            return None
        return self._U
    def _set_U(self, V):
        self._U = V
    U = property(_get_U, _set_U)    # 电压

    def _get_V1(self):
        return self._V1
    def _set_V1(self, V):
        self._V1 = V
    V1 = property(_get_V1, _set_V1)    # 左端电势

    def _get_V2(self):
        return self._V2
    def _set_V2(self, V):
        self._V2 = V
    V2 = property(_get_V2, _set_V2)    # 右端电势

    def info(self):
        pass


class PowerSource(ElectricalComponent):
    '''
    @brief 电源类
    '''
    Z = 0    # 电源的阻抗定义为 0

class IndependentVoltageSource(PowerSource):
    '''
    @brief 独立电压源类
    '''
    IMG_NAME = "U"

    def __init__(self, branch : ElectricalBranch, prefix : str = "U"):
        super().__init__(branch, prefix)
    
    def __str__(self):
        if self.U is not None:
            v, p = get_vp(self.U)
            u, unit = intelligent_output(v, V_table, V_k)
            return f"{self.prefix}{self.num} U={u:.2f}∠{p:.2f}° {unit}"
        else:
            return f"{self.prefix}{self.num}"
        

class IndependentCurrentSource(PowerSource):
    '''
    @brief 独立电流源类
    '''
    IMG_NAME = "I"

    def __init__(self, branch : ElectricalBranch, prefix : str = "I"):
        super().__init__(branch, prefix)
    
    def __str__(self):
        if self.I is not None:
            v, p = get_vp(self.I)
            i, unit = intelligent_output(v, I_table, I_k)
            return f"{self.prefix}{self.num} I={i:.2f}∠{p:.2f}° {unit}"
        else:
            return f"{self.prefix}{self.num}"
    
    def info(self):
        i = intelligent_output(self.I, I_table, I_k)
        return f"{i[0]:.3f}{i[1]}"

class DependentVoltageSource(PowerSource):
    '''
    @brief 受控电压源类
    @detail 受控电压源的电压由其他元件的电流或电压控制
    '''
    IMG_NAME = "kU"
    
    def __init__(self, branch : ElectricalBranch, prefix : str = "U"):
        super().__init__(branch, prefix)
        self.controler : ElectricalComponent = None    # 控制元件
        self.value : str = "U"                        # 控制量，U 或 I
        self.k : float = None                          # 增益系数

    def _get_U(self):
        if self.value == "U" and self.controler.U is not None:
            return self.k * self.controler.U
        elif self.value == "I" and self.controler.I is not None:
            return self.k * self.controler.I
    U = property(_get_U)    # 电压，只读

    def __str__(self):
        return f"{self.prefix}{self.num} U={self.k}{self.value}({self.controler})"

class DependentCurrentSource(PowerSource):
    '''
    @brief 受控电流源类
    @detail 受控电流源的电流由其他元件的电流或电压控制
    '''
    IMG_NAME = "kI"
    
    def __init__(self, branch : ElectricalBranch, prefix : str = "I"):
        super().__init__(branch, prefix)
        self.controler : ElectricalComponent = None    # 控制元件
        self.value : str = "U"                        # 控制量，U 或 I
        self.k : float = None                          # 增益系数
    
    def _get_I(self):
        if self.value == "U" and self.controler.U is not None:
            return self.k * self.controler.U
        elif self.value == "I" and self.controler.I is not None:
            return self.k * self.controler.I
    I = property(_get_I)    # 电流，只读

    def __str__(self):
        return f"{self.prefix}{self.num} I={self.k}{self.value}({self.controler})"

class Impedance(ElectricalComponent):
    '''
    @brief 通用阻抗元件
    @detail 继承自电气二端元件类，增加了阻抗属性
            可以描述任何一个无源线性二端口网络
    '''
    IMG_NAME = "Z"

    def __init__(self, branch : ElectricalBranch, prefix : str = "Z"):
        super().__init__(branch, prefix)
        self._Z : complex = None
    
    def _get_Z(self):
        return self._Z
    def _set_Z(self, Z):
        self._Z = Z
    Z : complex = property(_get_Z, _set_Z)     # 阻抗

    def _get_Y(self):
        return 1 / self.Z
    Y = property(_get_Y)    # 导纳，只读

    def __str__(self):
        if self.Z is not None:
            v, p = get_vp(self.Z)
            z, unit = intelligent_output(v, R_table, R_k)
            return f"{self.prefix}{self.num} Z={z:.2f}∠{p:.2f}° {unit}"
        else:
            return f"{self.prefix}{self.num}"

class Resistor(Impedance):
    '''
    @brief 电阻类
    @detail 继承自通用阻抗元件类，增加了电阻属性
    '''
    IMG_NAME = "R"

    def __init__(self, branch : ElectricalBranch, prefix : str = "R"):
        super().__init__(branch, prefix)
        self._R = None

    def _get_R(self):
        return self._R
    def _set_R(self, R):
        self._R = R
    R = property(_get_R, _set_R)     # 电阻

    def _get_Z(self):
        return self.R
    Z = property(_get_Z)    # 阻抗，只读

    def __str__(self):
        if self.R is not None:
            r = intelligent_output(self.R, R_table, R_k)
            return f"{self.prefix}{self.num} R={r[0]:.2f}{r[1]}"
        else:
            return f"{self.prefix}{self.num}"

class Capacitor(Impedance):
    '''
    @brief 电容类
    @detail 继承自通用阻抗元件类，增加了电容属性
    '''
    IMG_NAME = "C"

    def __init__(self, branch : ElectricalBranch, prefix : str = "C"):
        super().__init__(branch, prefix)
        self._C = None

    def _get_C(self):
        return self._C
    def _set_C(self, C):
        self._C = C
    C = property(_get_C, _set_C)    # 电容

    def _get_Z(self):
        return 1 / (1j * self.C * OMEGA)
    Z = property(_get_Z)    # 阻抗，只读

    def __str__(self):
        if self.C is not None:
            c = intelligent_output(self.C, C_table, C_k)
            return f"{self.prefix}{self.num} C={c[0]:.2f}{c[1]}"
        else:
            return f"{self.prefix}{self.num}"

class Inductor(Impedance):
    '''
    @brief 电感类
    @detail 继承自通用阻抗元件类，增加了电感属性
    '''
    IMG_NAME = "L"

    def __init__(self, branch : ElectricalBranch, prefix : str = "L"):
        super().__init__(branch, prefix)
        self._L = None

    def _get_L(self):
        return self._L
    def _set_L(self, L):
        self._L = L
    L = property(_get_L, _set_L)     # 电感

    def _get_Z(self):
        return 1j * self.L * OMEGA
    Z = property(_get_Z)    # 阻抗，只读

    def __str__(self):
        if self.L is not None:
            l = intelligent_output(self.L, L_table, L_k)
            return f"{self.prefix}{self.num} L={l[0]:.2f}{l[1]}"
        else:
            return f"{self.prefix}{self.num}"

node_0 = ElectricalNode(0)    # 参考节点
node_0.V = 0                  # 参考节点电压为0
node_1 = ElectricalNode(1)    # 节点1
node_2 = ElectricalNode(2)    # 节点2
node_3 = ElectricalNode(3)    # 节点3
nodes = [node_0, node_1, node_2, node_3]

# 以下为测试用的电路结构搭建
'''
b = ElectricalBranch(node_0, node_1)
c = IndependentVoltageSource(b)
b.append(c)
c.U = 100
b = ElectricalBranch(node_0, node_2)
c = Resistor(b)
c.R = 1
b.append(c)
c = IndependentVoltageSource(b)
c.U = 90
b.append(c)
b = ElectricalBranch(node_0, node_3)
c = Resistor(b)
c.R = 1
b.append(c)
c = IndependentCurrentSource(b)
c.I = 20
b.append(c)
b = ElectricalBranch(node_1, node_2)
c = IndependentVoltageSource(b)
c.U = 110
b.append(c)
b = ElectricalBranch(node_1, node_3)
c = Resistor(b)
c.R = 2
b.append(c)
b = ElectricalBranch(node_2, node_3)
c = Resistor(b)
c.R = 2
b.append(c)
del b, c
# '''

if __name__ == "__main__":
    # 测试
    print(intelligent_output(0.001, V_table, V_k))